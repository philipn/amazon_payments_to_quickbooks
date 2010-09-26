"""
LICENSE: public domain.

Converts an amazon payments .csv file to a quickbooks-compatible .iif file.

An .iif file has a format like:

!TRNS	DATE	ACCNT	NAME	CLASS	AMOUNT	MEMO
!SPL	DATE	ACCNT	NAME	AMOUNT	MEMO
!ENDTRNS
TRNS	"9/24/2010"	"Paypal"	"grommit"	"Web Accept Payment Received"	48.25	"Wiki Spot c/o Wiki Spot"	
SPL	"9/24/2010"	"Other Income"	"grommit"	-50.00
SPL	"9/24/2010"	"Other Expenses"	Fee	1.75
ENDTRNS
TRNS	"9/1/2010"	"Paypal"	"PayPal - Money Market"	"Dividend From PayPal Money Market"	0.01	
SPL	"9/1/2010"	"Other Income"	"PayPal - Money Market"	-0.01
ENDTRNS
TRNS	"8/8/2010"	"Paypal"	"Cernio Technology Cooperative"	"Shopping Cart Payment Sent"	-100.00	"Shopping Cart"	
SPL	"8/8/2010"	"Other Expenses"	"Cernio Technology Cooperative"	100.00
ENDTRNS
TRNS	"8/5/2010"	"Paypal"	"PayPal - Money Market"	"Dividend From PayPal Money Market"	0.02	
SPL	"8/5/2010"	"Other Income"	"PayPal - Money Market"	-0.02
ENDTRNS


amazon CSV looks like:

"Date","Type","To/From","Name","Status","Amount","Fees","Transaction ID"
"Sep 25, 2010","Withdrawal","To","Wiki Spot","Initiated","$23,724.88","$0.00","15D5J2SL11UN7VLTAJA7C2F2GHVJDGTENS8"
"Sep 20, 2010","Payment","From","Scott Meehleib","Failed","$100.00","$3.20","15CODDSKP5U9KNF8LGBEAJBRU3CR81CMI86"
"Sep 20, 2010","Payment","To","Kickstarter","Completed","$1.00","$0.00","15CODE7ZP18GDUJMAQA5UO9E3R5FAT62QFM"
"""

ACCOUNT = "Amazon Payments"
# Our expense account, in our case, payments to Kickstarter.com - Fundraising Fees
EXPENSES = "Contract Services:Fundraising Fees"
# We're making amazon payment fees as Banking Fees
PAYMENT_FEES = "Business Expenses:Banking Fees"
# Our income account, in our case, is our individual contribution/donation account
INCOME = "Direct Public Support:Individ, Business Contributions"

import csv
import sys
import datetime
import locale

locale.setlocale( locale.LC_ALL, '' )

filename = sys.argv[1]
iif_out = open('amazon.iif', 'w')

def get_customers(filename):
    customers = []
    f = open(filename, 'r')
    reader = csv.reader(f)
    reader.next()
    for row in reader:
        date_str, type, to_or_from, name, status, amount, fees, transaction_id = row
        customers.append(name)
    f.close()
    return list(set(customers))

customers = get_customers(filename)

def write_iif_header():
    iif_out.write("""!TRNS	DATE	ACCNT	NAME	CLASS	AMOUNT	MEMO\n""")
    iif_out.write("""!SPL	DATE	ACCNT	NAME	AMOUNT	MEMO
!ENDTRNS\n""")
    iif_out.write("""!CUST	NAME\n""")
    for customer in customers:
        iif_out.write("""CUST	%s\n""" % customer)

def parse_amount(amount):
    num = float(amount[1:].replace(',',''))
    return (num, locale.currency(num)[1:])

def process_payment(transaction_date, to_or_from, name, amount, fees, transaction_id):
    date = "%s/%s/%s" % (
        transaction_date.month, transaction_date.day, transaction_date.year
    )
    fee_num, fee_amount = parse_amount(fees)
    direct_amount_num, direct_amount = parse_amount(amount)
    rough_total += direct_amount_num
    total_amount = locale.currency(direct_amount_num - fee_num)[1:]
    payment_details = {
        'date': date,
        'account': ACCOUNT,
        'name': name,
        'comment': "Amazon payment",
        'total_amount': total_amount,
        'income_account': INCOME,
        'direct_amount': direct_amount,
        'expense_account': EXPENSES,
        'fee_amount': fee_amount,
        'fee_account': PAYMENT_FEES,
    }
    if to_or_from == 'From':
        payment_str = """TRNS	"%(date)s"	"%(account)s"	"%(name)s"	"%(comment)s"	%(total_amount)s	"Amazon payment"	
SPL	"%(date)s"	"%(income_account)s"	"%(name)s"	-%(direct_amount)s
SPL	"%(date)s"	"%(fee_account)s"	Fee	%(fee_amount)s
ENDTRNS""" % payment_details
        exact_total += (direct_amount_num - fee_num)
    elif to_or_from == 'To':
        payment_str = """TRNS	"%(date)s"	"%(account)s"	"%(name)s"	"%(comment)s"	-%(total_amount)s	"Amazon payment"	
SPL	"%(date)s"	"%(expense_account)s"	"%(name)s"	%(direct_amount)s
SPL	"%(date)s"	"%(fee_account)s"	Fee	%(fee_amount)s
ENDTRNS""" % payment_details
        exact_total -= (direct_amount_num - fee_num)

    iif_out.write(payment_str + '\n')

def process_withdrawal(transaction_date, to_or_from, name, amount, fees, transaction_id):
    """
    We skip these because we assume they can be marked from the relevant bank account import.

    PayPal doesn't export bank account transfers in their .iif files and it all works out.
    """
    pass

reader = csv.reader(open(filename, 'r'))
reader.next()
write_iif_header()
for row in reader:
    date_str, type, to_or_from, name, status, amount, fees, transaction_id = row
    transaction_date = datetime.datetime.strptime(date_str, '%b %d, %Y')
    # skip transactions that didn't go through
    # it seems that amazon lists transactions as 'initiated' that are
    # actually successful.  we don't import failed ones, though..
    if status != 'Completed':
        continue
    if type == 'Payment':
        process_payment(transaction_date, to_or_from, name, amount, fees, transaction_id)
    elif type == 'Withdrawal':
        process_withdrawal(transaction_date, to_or_from, name, amount, fees, transaction_id)
