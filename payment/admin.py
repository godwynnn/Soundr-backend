from django.contrib import admin
from payment.models import Transaction, Wallet, BankAccount, Beneficiary
# Register your models here.

admin.site.register(Transaction)
admin.site.register(Wallet)
admin.site.register(BankAccount)
admin.site.register(Beneficiary)
    