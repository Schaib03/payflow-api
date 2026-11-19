from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce

from ledger.models import Direction, LedgerEntry, LedgerTransaction


class Command(BaseCommand):
    help = "Check that every ledger transaction balances and that the ledger as a whole sums to 0."

    def handle(self, *args, **options):
        debit = Coalesce(Sum("entries__amount", filter=Q(entries__direction=Direction.DEBIT)), 0)
        credit = Coalesce(Sum("entries__amount", filter=Q(entries__direction=Direction.CREDIT)), 0)
        problems = list(
            LedgerTransaction.objects.annotate(debits=debit, credits=credit)
            .exclude(debits=F("credits"))
            .values_list("id", "debits", "credits")
        )
        for txn_id, debits, credits in problems:
            self.stderr.write(f"Unbalanced transaction {txn_id}: debits={debits} credits={credits}")

        totals = LedgerEntry.objects.values("account__currency", "direction").annotate(
            total=Sum("amount")
        )
        per_currency = {}
        for row in totals:
            sign = 1 if row["direction"] == Direction.DEBIT else -1
            currency = row["account__currency"]
            per_currency[currency] = per_currency.get(currency, 0) + sign * row["total"]
        for currency, net in sorted(per_currency.items()):
            self.stdout.write(f"{currency}: debits - credits = {net}")
            if net != 0:
                problems.append(currency)

        if problems:
            raise CommandError(f"Ledger check failed ({len(problems)} problem(s)).")
        self.stdout.write(self.style.SUCCESS("Ledger is balanced."))
