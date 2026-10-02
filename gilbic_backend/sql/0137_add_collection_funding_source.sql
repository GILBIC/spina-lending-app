BEGIN;

-- Recorder attribution is not cash custody. Existing rows remain physical cash.
ALTER TABLE lending.collection_transactions
 ADD COLUMN funding_source text NOT NULL DEFAULT 'collector_cash'
   CHECK(funding_source IN ('collector_cash','treasury_receipt')),
 ADD COLUMN funding_receipt_id uuid REFERENCES treasury.receipts(id),
 ADD COLUMN funding_account_id uuid REFERENCES treasury.accounts(id),
 ADD CONSTRAINT collection_funding_identity CHECK (
  (funding_source='collector_cash' AND funding_receipt_id IS NULL AND funding_account_id IS NULL)
  OR (funding_source='treasury_receipt' AND funding_receipt_id IS NOT NULL AND funding_account_id IS NOT NULL));

CREATE FUNCTION lending.capture_treasury_collection_funding() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,lending,treasury AS $$
DECLARE receipt treasury.receipts%ROWTYPE; receipt_id uuid; used numeric(18,2);
BEGIN
 receipt_id := nullif(current_setting('spina.treasury_receipt_id',true),'')::uuid;
 IF receipt_id IS NULL THEN
  IF NEW.funding_source<>'collector_cash' OR NEW.funding_receipt_id IS NOT NULL OR NEW.funding_account_id IS NOT NULL THEN
   RAISE EXCEPTION 'Treasury funding requires its protected receipt transaction';
  END IF;
  RETURN NEW;
 END IF;
 SELECT * INTO receipt FROM treasury.receipts WHERE id=receipt_id FOR UPDATE;
 IF NOT FOUND OR receipt.client_id<>NEW.client_id OR NEW.entry_type='pass' THEN
  RAISE EXCEPTION 'Treasury receipt does not match this payment';
 END IF;
 IF EXISTS(SELECT 1 FROM treasury.event_revisions WHERE event_id=receipt.event_id AND action='correct') THEN
  RAISE EXCEPTION 'A corrected receipt is not available for application';
 END IF;
 SELECT coalesce(sum(amount),0) INTO used FROM lending.collection_transactions
 WHERE funding_receipt_id=receipt.id AND NOT is_voided;
 IF used+NEW.amount>receipt.amount-receipt.refunded_amount THEN
  RAISE EXCEPTION 'Treasury receipt application exceeds its remaining funds';
 END IF;
 NEW.funding_source := 'treasury_receipt';
 NEW.funding_receipt_id := receipt.id;
 NEW.funding_account_id := receipt.account_id;
 NEW.details := coalesce(NEW.details,'{}'::jsonb)||jsonb_build_object('funding_source','treasury_receipt');
 RETURN NEW;
END $$;
-- PostgreSQL runs same-event triggers alphabetically, before assignment capture.
CREATE TRIGGER lending_00_treasury_funding BEFORE INSERT ON lending.collection_transactions
FOR EACH ROW EXECUTE FUNCTION lending.capture_treasury_collection_funding();

CREATE FUNCTION lending.guard_treasury_collection_funding() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,lending AS $$
BEGIN
 IF (NEW.funding_source,NEW.funding_receipt_id,NEW.funding_account_id)
  IS DISTINCT FROM (OLD.funding_source,OLD.funding_receipt_id,OLD.funding_account_id) THEN
  RAISE EXCEPTION 'Collection funding history is immutable';
 END IF;
 IF OLD.funding_source='treasury_receipt' THEN
  IF NEW.remittance_id IS NOT NULL OR NEW.is_locked THEN
   RAISE EXCEPTION 'Owner-received funds cannot enter Collector cash custody';
  END IF;
  IF (NEW.amount,NEW.client_id,NEW.loan_id)
   IS DISTINCT FROM (OLD.amount,OLD.client_id,OLD.loan_id) THEN
   RAISE EXCEPTION 'Correct treasury-funded payments through the receipt workflow';
  END IF;
  IF (NEW.applied_amount,NEW.unallocated_amount) IS DISTINCT FROM (OLD.applied_amount,OLD.unallocated_amount)
    AND coalesce(current_setting('spina.treasury_receipt_id',true),'')<>OLD.funding_receipt_id::text
    AND coalesce(current_setting('spina.treasury_application_reversal',true),'')<>'on' THEN
   RAISE EXCEPTION 'Allocation changes require the protected treasury transaction';
  END IF;
  IF NEW.is_voided IS DISTINCT FROM OLD.is_voided AND
     coalesce(current_setting('spina.treasury_application_reversal',true),'')<>'on' THEN
   RAISE EXCEPTION 'Reverse treasury application through its protected receipt workflow';
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER accounting_00a_treasury_funding_guard BEFORE UPDATE ON lending.collection_transactions
FOR EACH ROW EXECUTE FUNCTION lending.guard_treasury_collection_funding();

-- Existing cash notifications remain byte-for-byte behavior for cash. They must
-- never describe an owner-wallet payment as money held by the recording person.
DROP TRIGGER lending_collection_posted_activity ON lending.collection_transactions;
CREATE TRIGGER lending_collection_posted_activity AFTER INSERT ON lending.collection_transactions
FOR EACH ROW WHEN (NEW.funding_source='collector_cash')
EXECUTE FUNCTION core.create_collection_posted_activity();
DROP TRIGGER lending_management_direct_payment_activity ON lending.collection_transactions;
CREATE TRIGGER lending_management_direct_payment_activity AFTER INSERT ON lending.collection_transactions
FOR EACH ROW WHEN (NEW.funding_source='collector_cash')
EXECUTE FUNCTION core.create_management_direct_assignment_activity();

CREATE FUNCTION core.create_treasury_payment_activity() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,core,lending AS $$
DECLARE borrower_user uuid;
BEGIN
 SELECT user_id INTO borrower_user FROM lending.clients WHERE id=NEW.client_id;
 IF borrower_user IS NOT NULL THEN
  INSERT INTO core.activity_notifications(recipient_user_id,sender_user_id,notification_type,title,message,transaction_id,client_id,metadata)
  VALUES(borrower_user,NEW.collector_user_id,'client_payment_posted','Verified recipient funds applied',
    format('PHP %s from verified recipient-account funds was applied to your loan. Receipt %s. This is not a Collector cash handover.',NEW.amount,NEW.receipt_number),
    NEW.id,NEW.client_id,jsonb_build_object('receipt_number',NEW.receipt_number,'amount',NEW.amount::text,
      'loan_id',NEW.loan_id,'funding_source','treasury_receipt')) ON CONFLICT DO NOTHING;
 END IF;
 IF NEW.assigned_collector_user_id IS NOT NULL AND NEW.assigned_collector_user_id<>NEW.collector_user_id THEN
  INSERT INTO core.activity_notifications(recipient_user_id,sender_user_id,notification_type,title,message,transaction_id,client_id,metadata)
  VALUES(NEW.assigned_collector_user_id,NEW.collector_user_id,'cross_collection_posted','Verified recipient funds applied',
    format('Verified recipient-account funds of PHP %s were applied to an assigned borrower loan. Receipt %s. No cash handover is due from you.',NEW.amount,NEW.receipt_number),
    NEW.id,NEW.client_id,jsonb_build_object('receipt_number',NEW.receipt_number,'amount',NEW.amount::text,
      'loan_id',NEW.loan_id,'funding_source','treasury_receipt')) ON CONFLICT DO NOTHING;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER lending_treasury_payment_activity AFTER INSERT ON lending.collection_transactions
FOR EACH ROW WHEN (NEW.funding_source='treasury_receipt')
EXECUTE FUNCTION core.create_treasury_payment_activity();
REVOKE ALL ON FUNCTION core.create_treasury_payment_activity() FROM PUBLIC;

CREATE FUNCTION lending.guard_treasury_remittance_item() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,lending AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM lending.collection_transactions WHERE id=NEW.transaction_id AND funding_source<>'collector_cash') THEN
  RAISE EXCEPTION 'Treasury-funded payment is not a Collector cash handover';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER treasury_remittance_item_guard BEFORE INSERT OR UPDATE ON lending.collection_remittance_items
FOR EACH ROW EXECUTE FUNCTION lending.guard_treasury_remittance_item();

-- Existing collection journals have a Collector-cash debit, not an account/context
-- binding. Keep them blocked for treasury funding until an explicit mapping exists.
CREATE FUNCTION accounting.guard_treasury_collection_journal() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,lending,accounting AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM lending.collection_transactions t
           WHERE NEW.source_event_key='collection:'||t.id::text AND t.funding_source='treasury_receipt') THEN
  RAISE EXCEPTION 'Treasury collection requires a reviewed account and legal-context journal mapping';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER treasury_collection_journal_guard BEFORE INSERT OR UPDATE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_treasury_collection_journal();

CREATE INDEX collection_treasury_receipt_idx ON lending.collection_transactions(funding_receipt_id)
WHERE funding_receipt_id IS NOT NULL;
COMMENT ON COLUMN lending.collection_transactions.funding_source IS
'Immutable actual funding source. Must remain honored when treasury entry is disabled; downgrade to a cash-only reader is unsafe.';
REVOKE ALL ON FUNCTION lending.capture_treasury_collection_funding(),
 lending.guard_treasury_collection_funding(), lending.guard_treasury_remittance_item(),
 accounting.guard_treasury_collection_journal() FROM PUBLIC;
COMMIT;
