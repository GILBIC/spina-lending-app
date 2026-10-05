BEGIN;

-- Existing captures were accepted only with an explicit wet-signature witness.
-- Preserve them as paper scans; screen signatures are a separate recorded method.
ALTER TABLE lending.office_review_evidence
    ADD COLUMN capture_method TEXT NOT NULL DEFAULT 'paper_scan';
ALTER TABLE lending.office_review_evidence
    ADD CONSTRAINT office_review_evidence_capture_method CHECK (
        capture_method = 'paper_scan' OR (
            capture_method = 'screen_signature'
            AND purpose IN ('cif_review', 'application_review', 'privacy_acknowledgment')
            AND media_type = 'image/png'
        )
    );

COMMENT ON COLUMN lending.office_review_evidence.capture_method IS
    'Witnessed capture method. captured_at is server receipt time, not an independently verified signing time.';

COMMIT;
