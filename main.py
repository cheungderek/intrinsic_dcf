# Derek - 11 Dec 2020
# 8 Jan 2020
# https://medium.com/analytics-vidhya/building-an-intrinsic-value-calculator-with-python-7986833962cd
# http://theautomatic.net/yahoo_fin-documentation/
# https://www.mattbutton.com/2019/01/24/how-to-scrape-yahoo-finance-and-extract-fundamental-stock-market-data-using-python-lxml-and-pandas/?fbclid=IwAR3971b38GYY7ERRLHB388ywzsGlEtd4heXj0191yJDgwdlHQFaKqwF99vI
# https://algotrading101.com/learn/yfinance-guide/

''' --- Steps --- '''
''' 
Overview
========
Find the net present value (PV) of a company by using forecasted Free Cash Flow (FCF) and its perpetual value.  
This is the net PV of the company and the intrinsic value of each share of the company can be found by dividing the PV 
of the company with the number of shares outstanding

FCF = EBIT - capital expenditure. The program assumes matured companies have less capital expenditure and thus FCF = EBIT.

To calculate future FCFs or EBITs, we will assume that the average revenue growth rate and the average EBIT margin of 
the company in the past three years will continue to apply for the next five years. Therefore, for a given future 
Revenue forecast using the previous average revenue growth rate, we can calculate the future EBIT assming the previous
EBIT margin (per revenue) is maintained. 

TTM is updated frequently on Yahoo finance and thus this program can reflect the latest intrinsic value of a company

Procedures
==========
1) From Income Statement
    - get the column header for the past 4 years + TTM such as 12/31/2016 ..... 12/31/2019, ttm
    - get the Total Revenue for each column
    - get the EBIT (e.g., Income Before Tax and Interest Expense) for each column
    - get the CAGR or Compound Annual Growth Rate. latest_rev/earliest_rev for each column
    
2) Forecasting Revenues and EBIT and use it to find the forecasted Free Cash Flow in the future
    - calculate the avg_EBIT_margin by adding all available EBIT / # columns. This is used to calculate the future
      FCF for a given future Revenue growth assuming the avg_EBIT_margin from the past few years maintains the same
    - calculate future forecast revenue, rev_forcast using CAGR. For example, to calculate the 2nd rev_forcast, 
      2nd forecast rev = rev (1 + CAGR) ^ 2
    - calculate EBIT_forecast or future FCF = rev_forecast_lst[i]*avg_EBIT_margin
    
3) Calculate Weighted Average Cost of Capital (average cost of capital of the firm with debt and equity financing
   and uses it as the discount rate to calculate PV of all future FCFs
   
   WACC = market_cap_int/company_value * equity_return + net_debt_int/company_value * debt_return * (1-tax_rate)
   
   WACC is the risk-adjusted discount rate. For example, a high-risk company will have a higher WACC because investors
   will demand higher interest rate of the company bond and equity financing????
'''

''' ---------- // ENHANCEMENT // ---------- 
This program is based on https://medium.com/analytics-vidhya/building-an-intrinsic-value-calculator-with-python-7986833962cd
with the following enhancements:
1)  include the net debt (short term cash - (short and long term debt) against the calculated Intrinsic Value of 
    the company. Otherwise, companies like Ford Motor (F) with over 120 billions debt could have a very high calculated 
    intrinsic value of USD 70 a share in early 2020 when it was only trading at 12% of its intrinsic value 
2)  For companies such as TD, TD.TO and 0700.HK in Yahoo Finance where Net Debt are not shown in the financial 
    statements, the original program will bomb. The folloiwng equation is used under this situation:
        XXXXXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
3)  Create a spreadsheet file with all Internet scraped, assumed and calculated values for the stock under analysis 
    for final sanity check
4)  incorporate Phil Town's 4 Rules to further evaluate the investement criteria of the stock such as quick ratio etc...
'''

from bs4 import BeautifulSoup as bs
import pandas as pd
import requests
import pandas_datareader as dr
import datetime
import lxml
from lxml import html
#from columnar import columnar
import openpyxl

'''---------- // Hard-coded variables below // ----------'''
company_ticker = 'GM'
#company_ticker = '9988.HK'
timespan = 100                      # timespan for the equity beta calculation
market_risk_premium = 0.0525        # required return rate
long_term_growth = 0.01             # perpetual 1% rate of return. Should be less than 2.5%
debt_return = 0.01
tax_rate = 0.3                      # 30% tax rate
'''---------- // Hard-coded variables above // ----------'''

def write_float_num(float_num, msg):
    tmp = ("{:.2f}".format(float_num * 100))
    f.write(msg + str(tmp) + '% \n')

'''----- // I. Financial Information from Yahoo Finance // -----'''
# Derek - try to get the following rows from the company's Income Statement
# row 0 - Income Statement's header such as years
# row 1 - Total Revenue
# row 2 - EBIT or (pre-tax income + interest paid)

filename = company_ticker + "_intrinsc_value.csv"
f = open(filename, "w")
f.write(company_ticker + '- Intrinsic Value Calculation \n')


income_statement_url = 'https://finance.yahoo.com/quote/' + company_ticker + '/financials?p=' + company_ticker
income_statement_html = requests.get(income_statement_url)
income_statement_soup = bs(income_statement_html.text, 'html.parser')

# build the Income Statement header and reverse the years"
income_statement_table = income_statement_soup.find('div', class_='M(0) Whs(n) BdEnd Bdc($seperatorColor) D(itb)')
income_statement_header = income_statement_table.find('div', class_='D(tbr) C($primaryColor)')
# Income Statement Header such as "Breakdown   x/x/2017   x/x/2018   x/x/2019   x/x/2020   TTM"
header_lst = []
for i in income_statement_header.find_all('div'):
    if len(i) != 0:
        header_lst.append(i.text)
header_lst = header_lst[::-1]
del header_lst[len(header_lst)-1]
header_lst.insert(0,'Breakdown')
income_statement_df = pd.DataFrame(columns = header_lst)

f.write(str(header_lst) + '\n')
#print(header_lst)

revenue_row = income_statement_table.find('div', class_='D(tbr) fi-row Bgc($hoverBgColor):h')
revenue_lst = []
for i in revenue_row.find_all('div', attrs={'data-test':'fin-col'}):
    i = i.text
    i = i.replace(",","")
    revenue_lst.append(int(i))
revenue_lst = revenue_lst[::-1]
f.write('Past Revenue (B), ' + str(['{:.1f}'.format(float(x) / 10 ** 6) for x in revenue_lst]) + '\n')
#print('Past Revenue (B) = ', str(['{:.1f}'.format(float(x) / 10 ** 6) for x in revenue_lst]), '\n')
revenue_lst.insert(0,'Total Revenue')
income_statement_df.loc[0] = revenue_lst


#income_statement_df.to_excel(writer, revenue_lst)

try:
    # in this program EBIT = FCF
    EBIT_row = income_statement_table.find('div', attrs={'title':'EBIT'}).parent.parent
except Exception as err:
    # some companies' Income Statement in Yahoo Finance such as TD, 0700.HK do not have EBIT. Use substitution:
    #   EBIT = Pretax Income + Interest Expense Non Operating
    # ToDo - find the Interest Expense Non Operating and add back to the PreTax Income
    EBIT_row = income_statement_table.find('div', attrs={'title': 'Pretax Income'}).parent.parent

EBIT_lst = []
for i in EBIT_row.find_all('div', attrs={'data-test':'fin-col'}):
    i = i.text
    i = i.replace(",","")
    EBIT_lst.append(int(i))
EBIT_lst = EBIT_lst[::-1]
f.write('Past EBIT (B), ' + str(['{:.1f}'.format(float(x) / 10 ** 6) for x in EBIT_lst]) + '\n')
EBIT_lst.insert(0,'EBIT')
income_statement_df.loc[1] = EBIT_lst


# Derek - remove the TTM column in both Total Revenue and EBIT
# May be include TTM so that there are more data points to calculate forecasted EBIT or FCF
income_statement_df = income_statement_df.drop('ttm', axis=1)


'''---------- // II. Forecasting Revenues and EBIT // ----------'''
# calculate average CAGR for Revenues for the past few years in order to use it for forecasting future revenues
latest_rev = income_statement_df.iloc[0,len(income_statement_df.columns)-1]
earliest_rev = income_statement_df.iloc[0,1]
# Derek - CAGR - Compound Annual Growth Rate
rev_CAGR = (latest_rev/earliest_rev)**(float(1/(len(income_statement_df.columns)-2)))-1
f.write('Revenue Compound Annual Growth Rate (CAGR) ,' + str("{:.1f}".format(rev_CAGR * 100)) + '% \n')
print('\n\nRevenue CAGR =', "{:.1f}".format(rev_CAGR * 100), '%')


EBIT_margin_lst = []
for year in range(1,len(income_statement_df.columns)):
    # EBIT / Revenue
    EBIT_margin = income_statement_df.iloc[1,year]/income_statement_df.iloc[0,year]
    EBIT_margin_lst.append(EBIT_margin)
avg_EBIT_margin = sum(EBIT_margin_lst)/len(EBIT_margin_lst)

f.write('Average EBIT Margin,' + str("{:.1f}".format(avg_EBIT_margin * 100)) + '% \n')

forecast_df = pd.DataFrame(columns=['Year ' + str(i) for i in range(1,7)])
f.write(',' + str(forecast_df.columns) + '\n')

rev_forecast_lst = []
f.write('Future CAGR Revenues (B) next 6 years,')
for i in range(1,7):
    if i != 6:
        rev_forecast = latest_rev*(1+rev_CAGR)**i
    else:
        rev_forecast = latest_rev*(1+rev_CAGR)**(i-1)*(1+long_term_growth)
    rev_forecast_lst.append(int(rev_forecast))
    #f.write(str(int(rev_forecast) / 10 ** 6) + ',')
f.write(str(['{:.1f}'.format(float(x) / 10 ** 6) for x in rev_forecast_lst]))
forecast_df.loc[0] = rev_forecast_lst
f.write('\n')


EBIT_forecast_lst = []
f.write('Future EBIT (B),')
for i in range(0,6):
    EBIT_forecast = rev_forecast_lst[i]*avg_EBIT_margin
    EBIT_forecast_lst.append(int(EBIT_forecast))
    #f.write(str(int(EBIT_forecast)) + ',')
f.write(str(['{:.1f}'.format(float(x) / 10 ** 6) for x in EBIT_forecast_lst]))
forecast_df.loc[1] = EBIT_forecast_lst



'''---------- // III. Calculating the WACC // ----------'''
# The Weighted Average Cost of Capital (WACC) is the cost of a firm to do business using debt and equity finance.
# WACC is used as the discount rate to discount future cash flows to the present value. It is very important and
# sensitivity in influencing the intrinsic value of the firm.
# Sanity Check - If a more credit worthy companies like Microsoft (MSFT) has WACC 7%, less worthy companies like
# Ford Moter (F) should have a higher WACC.
current_date = datetime.date.today()
past_date = current_date - datetime.timedelta(days=timespan)
f.write('\nLast 100 day average Risk Free Rate before ' + str(current_date))

# Derek - use ^TNX = 10 year Mortgage Rates for the past 100 days to calculate the Risk Free Rate for calculating
#       the WACC for discounting future FCFs to Present Value
risk_free_rate_df = dr.DataReader('^TNX', 'yahoo', past_date, current_date)
risk_free_rate_float = (risk_free_rate_df.iloc[len(risk_free_rate_df)-1,5])/100
f.write(str("{:.2f}".format(risk_free_rate_float * 100)) + '% \n')

price_information_df = pd.DataFrame(columns=['Stock Prices', 'Market Prices'])

stock_price_df = dr.DataReader(company_ticker, 'yahoo', past_date, current_date)
price_information_df['Stock Prices'] = stock_price_df['Adj Close']

# Derek - use ^GSPC = S&P 500 to calculate the expected stock rate of return for calculating the WACC for discounting
#       future FCFs to Present value
market_price_df = dr.DataReader('^GSPC', 'yahoo', past_date, current_date)
price_information_df['Market Prices'] = market_price_df['Adj Close']

returns_information_df = pd.DataFrame(columns =['Stock Returns', 'Market Returns'])

stock_return_lst = []
for i in range(1,len(price_information_df)):
    open_price = price_information_df.iloc[i-1,0]
    close_price = price_information_df.iloc[i,0]
    stock_return = (close_price-open_price)/open_price
    stock_return_lst.append(stock_return)
returns_information_df['Stock Returns'] = stock_return_lst

# uncomment to show Stock Return for calculating WACC
#f.write('Stock return ,' + str([('{:.2f}'.format(x * 100)) + '%' for x in stock_return_lst]) + '\n')


market_return_lst = []
for i in range(1,len(price_information_df)):
    open_price = price_information_df.iloc[i-1,1]
    close_price = price_information_df.iloc[i,1]
    market_return = (close_price-open_price)/open_price
    market_return_lst.append(market_return)
returns_information_df['Market Returns'] = market_return_lst

# Derek - uncomment to show Market Return for calculating WACC
#f.write('Market return ,' + str([('{:.2f}'.format(x * 100)) + '%' for x in market_return_lst]) + '\n')


covariance_df = returns_information_df.cov()
covariance_float = covariance_df.iloc[1,0]
variance_df = returns_information_df.var()
market_variance_float = variance_df.iloc[1]

equity_beta = covariance_float/market_variance_float
equity_return = risk_free_rate_float+equity_beta*(market_risk_premium)

f.write('Equity Beta ,' + str("{:.2f}".format(equity_beta)) + '\n')
f.write('Equity Return ,' + str("{:.2f}".format(equity_return * 100)) + '% \n')

balance_sheet_url = 'https://finance.yahoo.com/quote/' + company_ticker + '/balance-sheet?p=' + company_ticker
balance_sheet_html = requests.get(balance_sheet_url)
balance_sheet_soup = bs(balance_sheet_html.text, 'html.parser')

balance_sheet_table = balance_sheet_soup.find('div', class_='M(0) Whs(n) BdEnd Bdc($seperatorColor) D(itb)')

# Derek - Net Debt
# Not all companies' balance sheets have Net Debt. Therefore, we need to try a few ways to calculate the Net Debt
net_debt_lst = []
try:
    net_debt_row = balance_sheet_table.find('div', attrs={'title':'Net Debt'}).parent.parent
    for value in net_debt_row.find_all('div'):
        value = value.text
        value = value.replace(',', '')
        net_debt_lst.append(value)
    net_debt_int = int(net_debt_lst[3])
except Exception as err:
    # Derek - try to catch balance sheet that does not contain Net Debt
    # net debt = total debt - cash-like assets on the balance sheet

    total_debt_lst = []
    cash_equiv_lst = []
    total_debt_row = balance_sheet_table.find('div', attrs={'title':'Total Debt'}).parent.parent
    for total_debt_value in total_debt_row.find_all('div'):
        total_debt_value = total_debt_value.text
        total_debt_value = total_debt_value.replace(',', '')
        total_debt_lst.append(total_debt_value)
     # find the cash and cash equivalents
#    cash_equiv_row = balance_sheet_table.find_all('div', {"class":"DP(0) M(0) Va(m) Bd(0) Fz(s) Mend(2px) tgglBtn"}).parent.parent.parent
#    cash_equiv_row = balance_sheet_soup.find('div', attrs={'title':'Cash And Cash Equivalents'}).parent.parent
    cash_equiv_row = balance_sheet_soup.find('span', {'class':'Ta(c) Py(6px) Bxz(bb) BdB Bdc($seperatorColor) Miw(120px) Miw(140px)--pnclg D(tbc'})

    for cash_equiv_value in cash_equiv_row.find_all('div', attrs={'data-test':'fin-col'}):
        cash_equiv_value = cash_equiv_value.text
        cash_equiv_value = cash_equiv_value.replace(',', '')
        cash_equiv_lst.append(int(cash_equiv_value))
        cash_equiv_lst = cash_equiv_lst[::-1]
        cash_equiv_lst.insert(0, 'Total Cash Equiv')

    for value in total_debt_row.find_all('div'):
        net_debt_lst.append(value - cash_equiv_value)

#    income_statement_df.loc[0] = revenue_lst


# Derek - 2 Dec 2020 - Find the latest Share Issued in order to calculate the intrinsic value of each stock
shared_issued_lst = []
shared_issued_row = balance_sheet_table.find('div', attrs={'title':'Share Issued'}).parent.parent
for value in shared_issued_row.find_all('div'):
    value = value.text
    value = value.replace(',','')
    shared_issued_lst.append(value)
shared_issued_int = int(shared_issued_lst[3])

market_cap_url = 'https://finance.yahoo.com/quote/' + company_ticker + '?p=' + company_ticker
market_cap_html = requests.get(market_cap_url)
market_cap_soup = bs(market_cap_html.text, 'html.parser')

market_cap_int = 0

market_cap_row = market_cap_soup.find('td', attrs={'data-test':'MARKET_CAP-value'})
market_cap_str = market_cap_row.text
market_cap_lst = market_cap_str.split('.')

if market_cap_str[len(market_cap_str)-1] == 'T':
    market_cap_length = len(market_cap_lst[1])-1
    market_cap_lst[1] = market_cap_lst[1].replace('T',(9-market_cap_length)*'0')
    market_cap_int = int(''.join(market_cap_lst))

if market_cap_str[len(market_cap_str)-1] == 'B':
    market_cap_length = len(market_cap_lst[1])-1
    market_cap_lst[1] = market_cap_lst[1].replace('B',(6-market_cap_length)*'0')
    market_cap_int = int(''.join(market_cap_lst))

# company value = the total money needed to buy an entire company, which means we buy all share issues + the
# debt of the company. ???? So company likes FORD has 130 billion long-term debt make the company value
company_value = market_cap_int + net_debt_int

WACC = market_cap_int/company_value * equity_return + net_debt_int/company_value * debt_return * (1-tax_rate)
# Derek - Manual override of WACC is the value does not make sense. For example, if Ford Motor WACC is lower than
# Apply (e.g., WACC = 8%), you can manually override the calculated WACC by uncommenting next line where the example
# show WACC = 12%
#WACC = 0.12
f.write('Weighted Average Capital Cost (WACC),' + str("{:.2f}".format(WACC * 100)) + '% \n')
print('WACC = ', str("{:.1f}".format(WACC * 100)), '%')


'''-------- // IV. Discounting the Forecasted EBIT // --------'''
discounted_EBIT_lst = []

for year in range(0,5):
    discounted_EBIT = forecast_df.iloc[1,year]/(1+WACC)**(year+1)
    discounted_EBIT_lst.append(int(discounted_EBIT))

terminal_value = forecast_df.iloc[1,5]/(WACC-long_term_growth)
#print('terminal value of all future EBIT', terminal_value)
PV_terminal_value = int(terminal_value/(1+WACC)**5)
#print('present value of terminal value of future EBIT', PV_terminal_value)

enterprise_value = sum(discounted_EBIT_lst)+PV_terminal_value
equity_value = enterprise_value - net_debt_int
intrinsic_value = equity_value / shared_issued_int
f.write('Intrinsic value of each share of' + company_ticker + ',' + str("{:0.1f}".format(intrinsic_value)) + '\n')
print('Intrinsic value of each share of', company_ticker, 'on', current_date, '=', "{0:0.1f}".format(intrinsic_value), '\n')

f.close()




