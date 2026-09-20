"""Exact payroll snapshots, principal allocations and evidence-backed settlement."""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

from .employee_authorization import EmployeeAccessDenied
from .employee_operations import (
    MANILA,
    EmployeeConflict,
    day_pay,
    money,
    money_text,
    principal_installment,
    weekly_performance_benefit,
    weekly_tax,
)

LABELS = {
    "basic_pay": "Basic pay",
    "leave_pay": "Paid leave",
    "overtime": "Overtime",
    "premium_pay": "Holiday / rest-day premium",
    "performance_benefit": "Good Performance Benefits",
    "statutory": "Employee statutory contributions",
    "tax": "Withholding tax",
    "advance_repayment": "Agreed advance repayment",
    "thirteenth_month": "13th-month pay",
    "leave_conversion": "Unused leave conversion",
    "lawful_recovery": "Reviewed lawful recovery",
    "other": "Reviewed adjustment",
}


def _date(text):
    return date.fromisoformat(text)


def _amounts(payload):
    return {line["code"]: Decimal(line["amount"]) for line in payload["components"]}


def _components(amounts):
    return [
        {"code": code, "label": LABELS.get(code, code), "amount": money_text(value)}
        for code, value in amounts.items()
    ]


def _finish(payload, amounts):
    values = {k: money(v) for k, v in amounts.items()}
    gross = sum((v for v in values.values() if v > 0), Decimal(0))
    deductions = -sum((v for v in values.values() if v < 0), Decimal(0))
    if gross < deductions:
        raise EmployeeConflict(
            "The proposed deductions exceed available pay; review the installment or adjustment without creating negative wages"
        )
    payload.update(
        components=_components(values),
        gross_pay=money_text(gross),
        deductions=money_text(deductions),
        net_pay=money_text(gross - deductions),
        paid_amount="0.00",
        balance_due=money_text(gross - deductions),
    )
    return payload


def _reviewed_week(tx, c):
    start = c.week_start
    end = start + timedelta(days=6)
    if start.weekday() != 6:
        raise EmployeeConflict("Weekly payroll begins on Sunday and ends on Saturday")
    if end > tx.today:
        raise EmployeeConflict(
            "Complete the payroll week before calculating payable wages"
        )
    profile = tx.profile(c.employee_id)
    hire = _date(profile["payload"]["hire_date"])
    pending = [
        r
        for r in tx.all("requests", c.employee_id)
        if r["status"] == "pending"
        and start.isoformat() <= r["payload"].get("work_date", "") <= end.isoformat()
    ]
    if pending:
        raise EmployeeConflict(
            "Attendance, leave or overtime requests for this week still need review"
        )
    amounts = {
        k: Decimal(0) for k in ("basic_pay", "leave_pay", "overtime", "premium_pay")
    }
    gp = Decimal(0)
    days = []
    overtime_issues = []
    confirmed = any(
        r["status"] == "confirmed"
        and start.isoformat() <= r["payload"]["work_date"] <= end.isoformat()
        for r in tx.all("shortages", c.employee_id)
    )
    unresolved = [
        r
        for r in tx.all("shortages", c.employee_id)
        if r["status"] in ("reported", "responded")
        and start.isoformat() <= r["payload"]["work_date"] <= end.isoformat()
    ]
    # A reported discrepancy cannot erase a benefit. Owner resolves any dispute
    # separately; undisputed wages may proceed with the benefit at its current terms.
    for offset in range(7):
        day = start + timedelta(days=offset)
        if day < hire:
            continue
        p = tx.effective_profile(c.employee_id, day)
        schedule = tx.schedule(c.employee_id, day)
        rest = day.isoweekday() not in schedule["work_days"]
        calendar_rows = [
            r
            for r in tx.all("calendar")
            if r["payload"]["work_date"] == day.isoformat()
        ]
        if not calendar_rows:
            raise EmployeeConflict(
                f"Reviewed calendar classification is missing for {day}"
            )
        kind = calendar_rows[0]["payload"]["day_kind"]
        attendance = tx.attendance(c.employee_id, day)
        leaves = [
            r
            for r in tx.all("requests", c.employee_id)
            if r["status"] == "approved"
            and r["payload"]["request_kind"] == "leave"
            and r["payload"]["work_date"] == day.isoformat()
        ]
        leave = sum(r["payload"].get("paid_minutes", 0) for r in leaves)
        unpaid = sum(
            r["payload"]["minutes"]
            for r in leaves
            if r["payload"]["leave_kind"] == "unpaid"
        )
        unworked = day in c.unworked_holiday_dates
        if unworked and not c.unworked_holiday_basis:
            raise EmployeeConflict(
                "Unworked holiday pay needs reviewed eligibility evidence"
            )
        if attendance["status"] == "pending_review":
            if attendance["event_ids"]:
                raise EmployeeConflict(
                    f"Attendance on {day} is incomplete or conflicting; resolve the correction"
                )
            if not rest and leave + unpaid < 480 and not unworked:
                raise EmployeeConflict(
                    f"No accepted attendance or approved absence for scheduled day {day}"
                )
            working = 0
        else:
            working = attendance["working_minutes"]
        if working > 480:
            reviewed = sum(
                r["payload"]["minutes"]
                for r in tx.all("requests", c.employee_id)
                if r["status"] == "approved"
                and r["payload"]["request_kind"] == "overtime"
                and r["payload"]["work_date"] == day.isoformat()
            )
            if reviewed < working - 480:
                overtime_issues.append(
                    f"{day}: overtime needs review; recorded actual work remains included"
                )
        values = day_pay(
            daily_rate=Decimal(p["daily_rate"]),
            working_minutes=working,
            leave_minutes=leave,
            day_kind=kind,
            rest_day=rest,
            premium_pay_covered=p["premium_pay_covered"],
            holiday_pay_covered=p["holiday_pay_covered"],
            unworked_holiday=unworked,
        )
        for key, value in values.items():
            amounts[key] += value
        gp += weekly_performance_benefit(
            [working],
            confirmed_shortage=confirmed,
            partial_policy=p["gp_partial_day_policy"],
        )
        days.append(
            {
                "work_date": day.isoformat(),
                "working_minutes": working,
                "leave_minutes": leave,
                "daily_rate": p["daily_rate"],
                "day_kind": kind,
                "rest_day": rest,
                "amounts": {k: money_text(v) for k, v in values.items()},
            }
        )
    amounts["performance_benefit"] = gp
    p = tx.effective_profile(c.employee_id, end)
    return amounts, days, overtime_issues, unresolved, p


def _statutory_allocations(tx, employee_id, start, end, current_id):
    allocations = []
    months = sorted(
        {
            (start + timedelta(days=n)).replace(day=1)
            for n in range((end - start).days + 1)
        }
    )
    prior = [
        r
        for r in tx.all("payroll", employee_id)
        if r["id"] != str(current_id)
        and r["status"] in ("approved", "partially_paid", "paid")
    ]
    for month in months:
        rows = [
            r
            for r in tx.all("statutory_months", employee_id)
            if r["payload"]["month"] == month.isoformat()
        ]
        if not rows:
            raise EmployeeConflict(
                f"Reviewed employee and employer statutory inputs are missing for {month:%Y-%m}"
            )
        p = rows[0]["payload"]
        total = sum(
            (
                Decimal(p[k])
                for k in ("sss_employee", "philhealth_employee", "pagibig_employee")
            ),
            Decimal(0),
        )
        count = calendar.monthrange(month.year, month.month)[1]
        month_end = month.replace(day=count)
        if p.get("prior_employee_deductions") is None:
            raise EmployeeConflict(
                f"Reviewed prior employee deductions are required for {month:%Y-%m}, including an explicit zero"
            )
        previous = Decimal(p["prior_employee_deductions"]) + sum(
            (
                Decimal(a["amount"])
                for r in prior
                for a in r["payload"].get("statutory_allocations", [])
                if a["month"] == month.isoformat()
            ),
            Decimal(0),
        )
        if previous > total:
            raise EmployeeConflict(
                "Previously allocated monthly deductions exceed the reviewed total; record a reviewed correction"
            )
        days = (min(end, month_end) - max(start, month)).days + 1
        proposed = money(total * Decimal(days) / Decimal(count))
        # Final containing week reconciles rounding and any reviewed remaining amount.
        if end >= month_end:
            proposed = total - previous
        proposed = min(proposed, total - previous)
        allocations.append(
            {
                "month": month.isoformat(),
                "amount": money_text(proposed),
                "statutory_record_id": rows[0]["id"],
                "statutory_version": rows[0]["version"],
                "source": p["source"],
            }
        )
    return allocations


def _advance_allocations(tx, employee_id, end, current_id, available):
    allocations = []
    issues = []
    reserved = {}
    for row in tx.all("payroll", employee_id):
        if row["id"] == str(current_id) or row["status"] not in (
            "approved",
            "partially_paid",
        ):
            continue
        for allocation in row["payload"].get("advance_allocations", []):
            reserved[allocation["advance_id"]] = reserved.get(
                allocation["advance_id"], Decimal(0)
            ) + Decimal(allocation["amount"])
    for row in tx.all("advances", employee_id):
        if row["status"] != "disbursed":
            continue
        p = row["payload"]
        due = [i for i in p["installments"] if _date(i["due_date"]) <= end]
        agreed_due = sum((Decimal(i["amount"]) for i in due), Decimal(0))
        paid = Decimal(p["repaid_amount"]) - Decimal(p.get("terms_repaid_base", "0"))
        due_balance = max(
            Decimal(0), agreed_due - paid - reserved.get(row["id"], Decimal(0))
        )
        # Never automatically double a missed installment. Earliest unpaid single
        # installment requires review before changing the employee's agreement.
        remaining_paid = paid
        single = Decimal(0)
        for installment in due:
            amount = Decimal(installment["amount"])
            if remaining_paid >= amount:
                remaining_paid -= amount
            else:
                single = amount - remaining_paid
                break
        desired = min(due_balance, single)
        outstanding = max(
            Decimal(0),
            Decimal(p["outstanding_amount"]) - reserved.get(row["id"], Decimal(0)),
        )
        amount = principal_installment(desired, outstanding, available)
        if desired > 0 and amount == 0:
            issues.append(
                f"Advance {row['id']}: insufficient available pay; installment remains outstanding for review"
            )
        if amount:
            allocations.append(
                {
                    "advance_id": row["id"],
                    "version": row["version"],
                    "amount": money_text(amount),
                }
            )
            available -= amount
    return allocations, issues


def _annual_facts(tx, employee_id, as_of, current_id=None):
    year = as_of.year
    hire = _date(tx.profile(employee_id)["payload"]["hire_date"])
    histories = [
        r
        for r in tx.all("payroll_history", employee_id)
        if r["payload"]["year"] == year
    ]
    history = histories[0]["payload"] if histories else None
    if history and _date(history["through_date"]) > as_of:
        raise EmployeeConflict(
            "The imported historical summary extends after this calculation date; use a supported reviewed period"
        )
    cutoff = (
        _date(history["through_date"])
        if history
        else max(date(year, 1, 1), hire) - timedelta(days=1)
    )
    # A reviewed opening record is required for pre-system employment. Requiring
    # actual facts avoids treating absent historic salary as zero.
    rows = [
        r
        for r in tx.all("payroll", employee_id)
        if r["status"] in ("approved", "partially_paid", "paid")
        and r["payload"].get("payroll_kind") == "weekly"
        and cutoff < _date(r["payload"]["period_end"]) <= as_of
    ]
    cursor = cutoff + timedelta(days=1)
    intervals = sorted(
        [
            (_date(r["payload"]["week_start"]), _date(r["payload"]["period_end"]))
            for r in rows
        ]
    )
    for start, end in intervals:
        if start > cursor:
            raise EmployeeConflict(
                "Verified historical earnings are incomplete; import the reviewed year-to-date opening facts"
            )
        cursor = max(cursor, end + timedelta(days=1))
    if cursor <= as_of:
        raise EmployeeConflict(
            "Complete the current earned-pay period or import verified historic facts before annual/separation calculation"
        )
    basic = Decimal(history["basic_earned"]) if history else Decimal(0)
    taxable = Decimal(history["taxable_earned"]) if history else Decimal(0)
    withheld = Decimal(history["tax_withheld"]) if history else Decimal(0)
    thirteenth_paid = Decimal(history["thirteenth_paid"]) if history else Decimal(0)
    benefits = Decimal(history["other_benefits_paid"]) if history else Decimal(0)
    for row in rows:
        values = _amounts(row["payload"])
        basic += values.get("basic_pay", 0) + values.get("leave_pay", 0)
        taxable += Decimal(
            row["payload"].get("taxable_pay", row["payload"]["gross_pay"])
        )
        withheld -= values.get("tax", 0)
    for row in tx.all("payroll", employee_id):
        if (
            row["status"] in ("approved", "partially_paid", "paid")
            and row["payload"].get("payroll_kind") == "adjustment"
            and date(year, 1, 1) <= _date(row["payload"]["period_end"]) <= as_of
        ):
            adjustment_values = _amounts(row["payload"])
            basic += adjustment_values.get("basic_pay", 0) + adjustment_values.get(
                "leave_pay", 0
            )
            taxable += sum(
                (
                    adjustment_values.get(code, Decimal(0))
                    for code in (
                        "basic_pay",
                        "leave_pay",
                        "overtime",
                        "premium_pay",
                        "performance_benefit",
                        "other",
                    )
                ),
                Decimal(0),
            )
            if row["status"] == "paid":
                withheld -= adjustment_values.get("tax", 0)
        if (
            row["id"] != str(current_id)
            and row["status"] in ("approved", "partially_paid", "paid")
            and row["payload"].get("payroll_kind") in ("thirteenth_month", "separation")
            and _date(row["payload"]["period_end"]).year == year
        ):
            thirteenth_paid += _amounts(row["payload"]).get("thirteenth_month", 0)
    return {
        "basic": basic,
        "taxable": taxable,
        "withheld": withheld,
        "thirteenth_paid": thirteenth_paid,
        "benefits": benefits,
    }


def _annual_tax(taxable):
    brackets = [
        ("8000000", "2202500", ".35"),
        ("2000000", "402500", ".30"),
        ("800000", "102500", ".25"),
        ("400000", "22500", ".20"),
        ("250000", "0", ".15"),
    ]
    for threshold, base, rate in brackets:
        if taxable > Decimal(threshold):
            return money(Decimal(base) + (taxable - Decimal(threshold)) * Decimal(rate))
    return money(0)


def prepare(tx):
    c = tx.command
    tx.staff("prepare_payroll")
    tx.profile(c.employee_id)
    previous = tx.get("payroll", c.id, required=False)
    if previous and Decimal(previous["payload"].get("paid_amount", "0")) > 0:
        raise EmployeeConflict(
            "Paid or partially paid snapshots cannot be overwritten; create a linked adjustment"
        )
    if previous and previous["payload"].get("original_payroll_id"):
        raise EmployeeConflict(
            "A correction cannot be changed into an ordinary payroll run"
        )
    p = tx.command_payload()
    issues = []
    p["advance_allocations"] = []
    p["statutory_allocations"] = []
    if c.payroll_kind == "weekly":
        amounts, days, ot_issues, shortages, profile = _reviewed_week(tx, c)
        end = c.week_start + timedelta(days=6)
        p["days"] = days
        issues.extend(ot_issues)
        if shortages:
            issues.append(
                "Reported shortage is unresolved; benefit remains under existing terms pending owner decision"
            )
        allocations = _statutory_allocations(tx, c.employee_id, c.week_start, end, c.id)
        statutory = sum((Decimal(a["amount"]) for a in allocations), Decimal(0))
        p["statutory_allocations"] = allocations
        taxable = max(Decimal(0), sum(amounts.values(), Decimal(0)) - statutory)
        p["taxable_pay"] = money_text(taxable)
        tax = Decimal(0) if profile["tax_exempt"] else weekly_tax(taxable)
        if c.withholding_override is not None:
            if not c.withholding_basis:
                raise EmployeeConflict(
                    "A withholding override requires reviewed calculation evidence"
                )
            tax = c.withholding_override
        amounts["statutory"] = -statutory
        amounts["tax"] = -tax
        available = sum(amounts.values(), Decimal(0))
        advance_allocations, advance_issues = _advance_allocations(
            tx, c.employee_id, end, c.id, available
        )
        p["advance_allocations"] = advance_allocations
        issues.extend(advance_issues)
        amounts["advance_repayment"] = -sum(
            (Decimal(a["amount"]) for a in advance_allocations), Decimal(0)
        )
    elif c.payroll_kind == "leave_conversion":
        if c.leave_conversion_request_id is None:
            raise EmployeeConflict("Select an approved leave conversion request")
        request = tx.get("requests", c.leave_conversion_request_id)
        if (
            request["employee_id"] != str(c.employee_id)
            or request["status"] != "approved"
            or request["payload"]["request_kind"] != "leave_conversion"
        ):
            raise EmployeeConflict(
                "The leave conversion request is not eligible for settlement"
            )
        if any(
            r["id"] != str(c.id)
            and r["payload"].get("leave_conversion_request_id")
            == str(c.leave_conversion_request_id)
            and r["status"] not in ("rejected", "stale")
            for r in tx.all("payroll", c.employee_id)
        ):
            raise EmployeeConflict(
                "This leave conversion already has a payroll settlement"
            )
        end = _date(request["payload"]["as_of"])
        profile = tx.effective_profile(c.employee_id, end)
        amounts = {
            "leave_conversion": Decimal(profile["daily_rate"])
            * request["payload"]["minutes"]
            / 480
        }
        p["conversion_minutes"] = request["payload"]["minutes"]
        if c.withholding_override is None or not c.withholding_basis:
            raise EmployeeConflict(
                "Leave conversion requires reviewed tax treatment, including an explicit zero if applicable"
            )
        amounts["tax"] = -c.withholding_override
    else:
        end = c.week_start
        if end > tx.today:
            raise EmployeeConflict(
                "Annual or separation facts cannot include unearned future pay"
            )
        facts = _annual_facts(tx, c.employee_id, end, c.id)
        thirteenth = max(
            Decimal(0), money(facts["basic"] / 12) - facts["thirteenth_paid"]
        )
        amounts = {"thirteenth_month": thirteenth}
        profile = tx.effective_profile(c.employee_id, end)
        if c.payroll_kind == "separation":
            balance = tx.leave_balance(c.employee_id, end)
            amounts["leave_conversion"] = (
                Decimal(profile["daily_rate"]) * balance["available_minutes"] / 480
            )
            p["conversion_minutes"] = balance["available_minutes"]
        if c.withholding_override is not None:
            if not c.withholding_basis:
                raise EmployeeConflict(
                    "Annual/separation tax override needs reviewed reconciliation evidence"
                )
            amounts["tax"] = -c.withholding_override
        elif profile["tax_exempt"]:
            amounts["tax"] = Decimal(0)
        else:
            # Reviewed historical benefits remain explicit; do not infer exemption
            # from the name of an allowance or performance benefit.
            taxable_benefits = max(
                Decimal(0),
                facts["thirteenth_paid"]
                + thirteenth
                + facts["benefits"]
                - Decimal(90000),
            )
            total_tax = _annual_tax(
                facts["taxable"] + taxable_benefits + amounts.get("leave_conversion", 0)
            )
            amounts["tax"] = facts["withheld"] - total_tax
        p["annual_facts"] = {k: money_text(v) for k, v in facts.items()}
    fingerprint, versions = tx.fingerprint(c.employee_id, c.id)
    p.update(
        period_end=end.isoformat(),
        input_fingerprint=fingerprint,
        input_versions=versions,
        issues=issues,
    )
    recoveries = [
        r
        for r in tx.all("payroll", c.employee_id)
        if r["status"] == "allocated"
        and r["payload"].get("allocated_payroll_id") == str(c.id)
    ]
    for recovery in recoveries:
        shortage = tx.get("shortages", recovery["payload"]["shortage_id"])
        if shortage["status"] == "confirmed":
            amounts["lawful_recovery"] = amounts.get(
                "lawful_recovery", Decimal(0)
            ) + Decimal(recovery["payload"]["adjustment_amount"])
            p.setdefault("recovery_evidence", []).append(recovery["payload"])
        else:
            tx.save(
                "payroll",
                recovery["id"],
                c.employee_id,
                recovery["payload"],
                "cancelled",
                expected=recovery["version"],
            )
    _finish(p, amounts)
    return tx.save("payroll", c.id, c.employee_id, p, "draft")


def approve(tx):
    c = tx.command
    tx.staff("approve_payroll", c.employee_id)
    row = tx.get("payroll", c.id)
    tx.version(row)
    if row["status"] != "draft":
        raise EmployeeConflict("Only a current draft can be approved or rejected")
    p = row["payload"]
    if c.decision == "approved":
        if tx.fingerprint(c.employee_id, c.id)[0] != p["input_fingerprint"]:
            raise EmployeeConflict(
                "Payroll inputs changed; regenerate the draft before approving"
            )
        if any("overtime needs review" in issue for issue in p.get("issues", [])):
            raise EmployeeConflict(
                "Review the recorded overtime without discarding compensable work, then regenerate payroll"
            )
        end = _date(p["period_end"])
        if p.get("payroll_kind") == "weekly" and end == tx.today:
            schedule = tx.schedule(c.employee_id, end)
            if end.isoweekday() in schedule["work_days"] and datetime.now(
                MANILA
            ).time() < time.fromisoformat(schedule["end_time"]):
                raise EmployeeConflict(
                    "Saturday payroll approval waits until the scheduled shift is completed"
                )
    p.update(
        approved_by=str(tx.actor.user_id) if c.decision == "approved" else None,
        approval_reason=c.reason,
    )
    return tx.save("payroll", c.id, c.employee_id, p, c.decision)


def _settle_allocations(tx, row):
    p = row["payload"]
    employee_id = row["employee_id"]
    for a in p.get("advance_allocations", []):
        advance = tx.get("advances", a["advance_id"])
        v = advance["payload"]
        amount = Decimal(a["amount"])
        if amount > Decimal(v["outstanding_amount"]):
            raise EmployeeConflict(
                "Advance principal changed after payroll; reconcile the paid snapshot before settlement"
            )
        v["repaid_amount"] = money_text(Decimal(v["repaid_amount"]) + amount)
        v["outstanding_amount"] = money_text(Decimal(v["outstanding_amount"]) - amount)
        v["repayment_history"].append(
            {
                "amount": money_text(amount),
                "occurred_at": tx.command.occurred_at.isoformat(),
                "reference": row["id"],
                "source": "payroll",
            }
        )
        tx.save(
            "advances",
            advance["id"],
            employee_id,
            v,
            "repaid" if Decimal(v["outstanding_amount"]) == 0 else "disbursed",
            expected=advance["version"],
        )
    if p.get("conversion_minutes", 0):
        tx.save(
            "leave_ledger",
            uuid4(),
            employee_id,
            {
                "as_of": p["period_end"],
                "minutes": -p["conversion_minutes"],
                "kind": "conversion",
                "reason": "Settled unused leave conversion",
                "linked_payroll_id": row["id"],
            },
            "recorded",
            expected=0,
        )
        if p.get("leave_conversion_request_id"):
            request = tx.get("requests", p["leave_conversion_request_id"])
            tx.save(
                "requests",
                request["id"],
                employee_id,
                request["payload"],
                "settled",
                expected=request["version"],
            )


def payment(tx):
    c = tx.command
    tx.owner()
    row = tx.get("payroll", c.id)
    tx.version(row)
    p = row["payload"]
    if row["status"] not in ("approved", "partially_paid"):
        raise EmployeeConflict(
            "Only an approved payroll with an outstanding amount may be paid"
        )
    if (
        Decimal(p["paid_amount"]) == 0
        and tx.fingerprint(c.employee_id, c.id)[0] != p["input_fingerprint"]
    ):
        raise EmployeeConflict(
            "Payroll inputs changed; regenerate and reapprove before payment"
        )
    if c.amount > Decimal(p["balance_due"]) or (
        c.amount <= 0 and Decimal(p["net_pay"]) != 0
    ):
        raise EmployeeConflict(
            "The payment amount must be positive and cannot exceed unpaid approved pay"
        )
    if c.result == "completed":
        if c.payment_method == "cash" and not c.employee_acknowledgment:
            raise EmployeeConflict(
                "Completed cash payout requires the employee acknowledgment"
            )
        if c.payment_method != "cash" and (
            not c.reference or not c.settlement_evidence
        ):
            raise EmployeeConflict(
                "Completed transfer requires a reference and independently verified settlement evidence"
            )
        if c.payment_method != "cash" and any(
            r["status"] == "completed"
            and r["payload"].get("payroll_id") == str(c.id)
            and r["payload"].get("payment_method") == c.payment_method
            and r["payload"].get("reference", "").strip().casefold()
            == c.reference.strip().casefold()
            for r in tx.all("payments", c.employee_id)
        ):
            raise EmployeeConflict(
                "This completed salary transfer reference is already recorded"
            )
    attempt = tx.command_payload()
    attempt.update(
        payroll_id=str(c.id), recorded_by=str(tx.actor.user_id), payment_kind="salary"
    )
    tx.save("payments", c.request_id, c.employee_id, attempt, c.result, expected=0)
    if c.result != "completed":
        # Failed/pending evidence is real persisted history, never a successful pay.
        p["last_payment_result"] = c.result
        return tx.save("payroll", c.id, c.employee_id, p, row["status"])
    p["paid_amount"] = money_text(Decimal(p["paid_amount"]) + c.amount)
    p["balance_due"] = money_text(Decimal(p["net_pay"]) - Decimal(p["paid_amount"]))
    complete = Decimal(p["balance_due"]) == 0
    if complete:
        _settle_allocations(tx, row)
    result = tx.save(
        "payroll", c.id, c.employee_id, p, "paid" if complete else "partially_paid"
    )
    if complete:
        # New balance changes invalidate other unpaid snapshots, not this paid one.
        tx.invalidate(c.employee_id)
    return result


def adjustment(tx):
    c = tx.command
    tx.owner()
    original = tx.get("payroll", c.original_payroll_id)
    if original["employee_id"] != str(c.employee_id):
        raise EmployeeAccessDenied("The original payslip belongs to another employee")
    if original["status"] not in ("paid", "partially_paid"):
        raise EmployeeConflict(
            "Use recalculation/reapproval for unpaid payroll; adjustments require a paid original"
        )
    if c.expected_version != 0:
        raise EmployeeConflict(
            "A linked correction is a new immutable payroll snapshot"
        )
    if c.amount == 0:
        raise EmployeeConflict("A payroll adjustment must change an amount")
    if c.component == "lawful_recovery":
        if c.amount >= 0 or not all(
            (
                c.lawful_basis,
                c.responsibility_evidence,
                c.employee_response,
                c.maximum_authorized_recovery,
                c.shortage_id,
            )
        ):
            raise EmployeeConflict(
                "A loss recovery requires reviewed lawful basis, responsibility, response opportunity, actual case and authorized limit"
            )
        shortage = tx.get("shortages", c.shortage_id)
        if (
            shortage["employee_id"] != str(c.employee_id)
            or shortage["status"] != "confirmed"
        ):
            raise EmployeeConflict(
                "Loss recovery requires that employee's confirmed case"
            )
        recovered = -sum(
            (
                Decimal(r["payload"]["adjustment_amount"])
                for r in tx.all("payroll", c.employee_id)
                if r["status"] == "allocated"
                and r["payload"].get("shortage_id") == str(c.shortage_id)
            ),
            Decimal(0),
        )
        remaining = Decimal(shortage["payload"]["shortage_amount"]) - recovered
        if -c.amount > min(remaining, c.maximum_authorized_recovery):
            raise EmployeeConflict(
                "Recovery exceeds the actual unrecovered loss or reviewed authorized limit"
            )
        # A negative standalone payslip would manufacture negative wages. Record
        # recovery in the next positive unapproved weekly draft, never as advance.
        targets = [
            r
            for r in tx.all("payroll", c.employee_id)
            if r["status"] == "draft" and r["payload"].get("payroll_kind") == "weekly"
        ]
        if len(targets) != 1:
            raise EmployeeConflict(
                "Prepare one positive unpaid weekly draft for an authorized recovery allocation"
            )
        target = targets[0]
        p = target["payload"]
        amounts = _amounts(p)
        amounts["lawful_recovery"] = (
            amounts.get("lawful_recovery", Decimal(0)) + c.amount
        )
        _finish(p, amounts)
        p.setdefault("recovery_evidence", []).append(tx.command_payload())
        tx.save(
            "payroll",
            target["id"],
            c.employee_id,
            p,
            "draft",
            expected=target["version"],
        )
        evidence = tx.command_payload()
        evidence.update(
            original_payroll_id=str(c.original_payroll_id),
            adjustment_amount=money_text(c.amount),
            allocated_payroll_id=target["id"],
            payroll_kind="recovery_evidence",
            week_start=p["week_start"],
            period_end=p["period_end"],
            components=[],
            gross_pay="0.00",
            deductions="0.00",
            net_pay="0.00",
            paid_amount="0.00",
            balance_due="0.00",
            input_fingerprint=p["input_fingerprint"],
            input_versions=p["input_versions"],
            issues=[],
        )
        return tx.save("payroll", c.id, c.employee_id, evidence, "allocated")
    if c.amount < 0:
        raise EmployeeConflict(
            "A negative paid correction requires reviewed lawful recovery/offset handling, never an automatic clawback"
        )
    fingerprint, versions = tx.fingerprint(c.employee_id, c.id)
    p = tx.command_payload()
    p.update(
        original_payroll_id=str(c.original_payroll_id),
        adjustment_amount=money_text(c.amount),
        payroll_kind="adjustment",
        week_start=original["payload"]["week_start"],
        period_end=original["payload"]["period_end"],
        input_fingerprint=fingerprint,
        input_versions=versions,
        issues=[],
        advance_allocations=[],
        statutory_allocations=[],
    )
    _finish(p, {c.component: c.amount})
    return tx.save("payroll", c.id, c.employee_id, p, "draft")


def history_import(tx):
    c = tx.command
    tx.owner()
    tx.profile(c.employee_id)
    if c.through_date.year != c.year or c.through_date > tx.today:
        raise EmployeeConflict(
            "Historical payroll facts must belong to the selected year and not the future"
        )
    if tx.all("payroll_history", c.employee_id) and any(
        r["payload"]["year"] == c.year for r in tx.all("payroll_history", c.employee_id)
    ):
        raise EmployeeConflict(
            "Reviewed opening payroll history already exists for that year"
        )
    if any(
        r["payload"].get("payroll_kind") == "weekly"
        and _date(r["payload"]["week_start"]) <= c.through_date
        and _date(r["payload"]["period_end"]).year == c.year
        for r in tx.all("payroll", c.employee_id)
    ):
        raise EmployeeConflict(
            "Historical opening facts overlap recorded payroll periods"
        )
    row = tx.save(
        "payroll_history", c.id, c.employee_id, tx.command_payload(), "reviewed"
    )
    tx.invalidate(c.employee_id)
    return row


def execute_payroll_command(tx):
    handlers = {
        "payroll_prepare": prepare,
        "payroll_approve": approve,
        "payroll_payment": payment,
        "payroll_adjustment": adjustment,
        "payroll_history_import": history_import,
    }
    return handlers[tx.command.action](tx)
