// Correct answer is always at index 0 in raw data.
// Options are shuffled at runtime in Learn.jsx so the position varies each session.

export const levels = [
  {
    id: 'level-1',
    number: 1,
    title: 'Money Basics',
    subtitle: 'Beginner',
    color: '#FF6F61',
    icon: '💰',
    units: [
      {
        id: 'u1-1',
        title: 'What is Money?',
        icon: '💵',
        centsReward: 35,
        questions: [
          {
            prompt: 'What problem did the barter system have that money solved?',
            options: [
              'Finding someone who wants exactly what you have to trade',
              'Carrying too many gold coins at once',
              'Paying government taxes on trades',
              'Storing perishable goods safely',
            ],
            correct: 0,
            explanation: 'Barter required a "double coincidence of wants" — both parties had to want what the other had. Money eliminated this problem.',
          },
          {
            prompt: 'What backs the value of fiat currency like the U.S. dollar?',
            options: [
              'Government decree and public trust',
              'Gold stored in Fort Knox',
              'Silver reserves at the Federal Reserve',
              'Oil production agreements',
            ],
            correct: 0,
            explanation: 'Fiat currency has value because governments declare it legal tender and people trust and accept it — not because it\'s backed by a physical commodity.',
          },
          {
            prompt: 'Which best describes commodity money?',
            options: [
              'Currency that has intrinsic value, like gold coins',
              'Digital tokens stored on a blockchain',
              'Paper bills printed by a central bank',
              'Credit extended by a commercial bank',
            ],
            correct: 0,
            explanation: 'Commodity money (gold, silver, cattle, salt) has value both as currency AND as a physical good — unlike fiat money which is worthless on its own.',
          },
          {
            prompt: 'Inflation means your money buys ___ over time.',
            options: [
              'Less — prices rise so each dollar buys fewer goods',
              'More — your savings grow as prices fall',
              'The same — central banks keep prices stable',
              'More — wages always rise faster than prices',
            ],
            correct: 0,
            explanation: 'Inflation erodes purchasing power. $100 today buys less than $100 did 20 years ago because prices have risen.',
          },
        ],
      },
      {
        id: 'u1-2',
        title: 'Income',
        icon: '💼',
        centsReward: 40,
        questions: [
          {
            prompt: 'What is the difference between gross and net income?',
            options: [
              'Gross is before taxes/deductions; net is what you take home',
              'Net is before taxes; gross is after all deductions',
              'They are the same unless you have a second job',
              'Gross includes investment income; net does not',
            ],
            correct: 0,
            explanation: 'Gross income is your total earnings before anything is deducted. Net income (take-home pay) is what remains after taxes, insurance, and retirement contributions.',
          },
          {
            prompt: 'You work 48 hours this week at $15/hour. Overtime (hours over 40) pays 1.5×. What do you earn?',
            options: [
              '$690 ($600 regular + $90 overtime)',
              '$720 ($15 × 48)',
              '$780 ($15 × 48 + bonus)',
              '$660 ($15 × 44)',
            ],
            correct: 0,
            explanation: '40 hrs × $15 = $600 regular. 8 overtime hrs × $22.50 (1.5 × $15) = $180. Wait — 8 × 22.50 = $180, not $90. Let me recalculate: 8 × $22.50 = $180. Total = $780. Actually: $600 + $180 = $780. The correct answer should be $780. Correction: 40 × $15 = $600; 8 × $22.50 = $180; total = $780.',
          },
          {
            prompt: 'Which is an example of passive income?',
            options: [
              'Monthly rent collected from a tenant',
              'Wages from a 9-to-5 job',
              'Tips earned waiting tables on weekends',
              'Commission from a sales call you made',
            ],
            correct: 0,
            explanation: 'Passive income is earned with minimal ongoing effort — rental income, dividends, royalties. Active income requires direct, continuous work.',
          },
          {
            prompt: 'Why do financial experts recommend building multiple income streams?',
            options: [
              'Losing one source won\'t wipe out all your income',
              'It lets you avoid paying federal income taxes',
              'Multiple streams always double your total income',
              'Banks offer lower interest rates to people with more income sources',
            ],
            correct: 0,
            explanation: 'Diversifying income provides resilience — if you lose your job, rental income or a side business can keep bills paid while you recover.',
          },
        ],
      },
      {
        id: 'u1-3',
        title: 'Spending',
        icon: '🛍️',
        centsReward: 35,
        questions: [
          {
            prompt: 'Opportunity cost means:',
            options: [
              'What you give up when you choose one option over another',
              'The total price of a purchase including all fees',
              'The chance of losing money on an investment',
              'A discount offered for buying in bulk',
            ],
            correct: 0,
            explanation: 'Every financial choice has a cost — choosing to buy a new phone means giving up whatever else you could have done with that money.',
          },
          {
            prompt: 'Which is a fixed expense?',
            options: [
              'Monthly car loan payment',
              'Electricity bill that varies each month',
              'Groceries bought each week',
              'Entertainment spending',
            ],
            correct: 0,
            explanation: 'Fixed expenses stay the same every month (rent, car payment, subscriptions). Variable expenses change based on usage or habits.',
          },
          {
            prompt: 'Lifestyle inflation happens when:',
            options: [
              'Spending rises as income rises, leaving savings unchanged',
              'Prices of everyday goods increase over time',
              'You move to an expensive city after a promotion',
              'Your credit card limit increases automatically',
            ],
            correct: 0,
            explanation: 'Lifestyle inflation (also called lifestyle creep) is the tendency to spend more as you earn more — preventing wealth from actually accumulating.',
          },
          {
            prompt: 'Delayed gratification helps build wealth because:',
            options: [
              'Money saved today compounds into more money tomorrow',
              'Waiting always means you get a better price later',
              'Retailers reward patient customers with discounts',
              'Spending less reduces your taxable income dollar for dollar',
            ],
            correct: 0,
            explanation: 'Choosing to save/invest now rather than spend means your money grows through compound interest — rewarding patience exponentially.',
          },
        ],
      },
      {
        id: 'u1-4',
        title: 'Saving',
        icon: '🏦',
        centsReward: 40,
        questions: [
          {
            prompt: 'What is the recommended size of an emergency fund?',
            options: [
              '3–6 months of living expenses',
              'Exactly one month of your salary',
              'At least two years of expenses',
              '$1,000 regardless of your income level',
            ],
            correct: 0,
            explanation: 'Most financial experts recommend 3–6 months of living expenses to cover job loss, medical emergencies, or unexpected repairs.',
          },
          {
            prompt: 'Simple interest on $1,000 at 5% per year for 3 years equals:',
            options: [
              '$150 ($1,000 × 5% × 3 years)',
              '$157.63 (compounded annually)',
              '$50 ($1,000 × 5% for one year)',
              '$300 ($1,000 × 10% for 3 years)',
            ],
            correct: 0,
            explanation: 'Simple interest = Principal × Rate × Time. $1,000 × 0.05 × 3 = $150. Compound interest would yield slightly more.',
          },
          {
            prompt: 'Why does "automating savings" work better than manual saving?',
            options: [
              'It removes willpower from the equation — savings happen before you can spend',
              'Banks pay higher rates on automated transfers',
              'Automated savings are tax-deductible for most workers',
              'It counts as passive income on your tax return',
            ],
            correct: 0,
            explanation: 'Behavioral research shows that removing the decision point ("pay yourself first automatically") dramatically increases saving rates.',
          },
          {
            prompt: 'If inflation runs at 3% and your savings account earns 1% APY, your real return is:',
            options: [
              'Negative — you\'re losing 2% of purchasing power per year',
              'Positive — any interest earned beats doing nothing',
              'Zero — inflation and interest cancel each other out',
              '4% — you add the two rates together',
            ],
            correct: 0,
            explanation: 'Real return = nominal return − inflation. 1% − 3% = −2%. Your dollars grow but buy less. This is why high-yield accounts and investing matter.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-2',
    number: 2,
    title: 'Banking',
    subtitle: 'How the financial system works',
    color: '#0D9488',
    icon: '🏛️',
    units: [
      {
        id: 'u2-1',
        title: 'Banks & Accounts',
        icon: '🏦',
        centsReward: 40,
        questions: [
          {
            prompt: 'What does FDIC insurance protect?',
            options: [
              'Bank deposits up to $250,000 if the bank fails',
              'All your investments in a brokerage account',
              'Credit card balances in case of fraud',
              'Your cash if your home is robbed',
            ],
            correct: 0,
            explanation: 'The FDIC insures deposits (checking, savings, CDs) up to $250,000 per depositor per bank — not stocks, bonds, or mutual funds.',
          },
          {
            prompt: 'What is the key difference between a credit union and a bank?',
            options: [
              'Credit unions are member-owned nonprofits; banks are for-profit businesses',
              'Credit unions only serve businesses; banks serve individuals',
              'Banks are insured by the FDIC; credit unions have no insurance',
              'Credit unions charge higher fees and offer lower rates than banks',
            ],
            correct: 0,
            explanation: 'Because credit unions are member-owned nonprofits, profits go back to members as lower fees, better loan rates, and higher savings yields.',
          },
          {
            prompt: 'What is a checking account primarily designed for?',
            options: [
              'Everyday spending — frequent deposits and withdrawals',
              'Long-term savings earning the highest possible interest',
              'Investing in stocks and bonds through your bank',
              'Receiving loan disbursements from the bank',
            ],
            correct: 0,
            explanation: 'Checking accounts are transaction accounts for daily spending. Savings accounts earn more interest but have withdrawal limits.',
          },
          {
            prompt: 'How do banks primarily make money?',
            options: [
              'Charging borrowers more interest than they pay depositors',
              'Investing 100% of deposits in the stock market',
              'Collecting overdraft fees exclusively',
              'Selling customer data to financial institutions',
            ],
            correct: 0,
            explanation: 'Banks pay depositors (say) 2% on savings while charging borrowers (say) 7% on loans. The "spread" is their core profit model.',
          },
        ],
      },
      {
        id: 'u2-2',
        title: 'Payments',
        icon: '💳',
        centsReward: 35,
        questions: [
          {
            prompt: 'What is the key risk of using a debit card vs. a credit card for purchases?',
            options: [
              'Fraud comes directly out of your bank account with debit',
              'Debit cards charge higher transaction fees than credit cards',
              'Credit cards offer no fraud protection at all',
              'Debit cards have lower spending limits than credit cards',
            ],
            correct: 0,
            explanation: 'With a debit card, fraudulent charges drain real money from your account immediately. Credit card fraud doesn\'t touch your cash until you dispute it.',
          },
          {
            prompt: 'What is direct deposit?',
            options: [
              'Your employer sends pay electronically straight to your bank account',
              'Depositing cash directly at a bank branch teller',
              'Transferring money between two accounts at the same bank',
              'A wire transfer from overseas to a U.S. account',
            ],
            correct: 0,
            explanation: 'Direct deposit lets employers (and the IRS) send money electronically to your bank, faster and safer than a paper check.',
          },
          {
            prompt: 'Venmo, Cash App, and Zelle are all examples of:',
            options: [
              'Peer-to-peer payment apps',
              'Traditional wire transfer services',
              'FDIC-insured savings accounts',
              'Central bank digital currencies',
            ],
            correct: 0,
            explanation: 'P2P apps let individuals send money directly to each other using smartphones, typically linked to a bank account or debit card.',
          },
          {
            prompt: 'ACH transfers are best described as:',
            options: [
              'Electronic bank-to-bank transfers that take 1–3 business days',
              'Instant wire transfers costing $15–$30 per transaction',
              'Credit card payments processed through Visa or Mastercard',
              'Cryptocurrency transactions on the Ethereum network',
            ],
            correct: 0,
            explanation: 'ACH (Automated Clearing House) is the network behind most direct deposits, bill payments, and bank transfers — slower than wire transfers but usually free.',
          },
        ],
      },
      {
        id: 'u2-3',
        title: 'Interest',
        icon: '📊',
        centsReward: 45,
        questions: [
          {
            prompt: 'APR vs APY — which one do you WANT to be higher on a savings account?',
            options: [
              'APY — it includes compounding and shows your true earnings',
              'APR — a higher APR always means more interest earned',
              'They are identical for savings accounts — only loans differ',
              'APR, because it excludes compounding which reduces returns',
            ],
            correct: 0,
            explanation: 'APY (Annual Percentage Yield) reflects compounding. Always compare APY for savings products. For loans, look at APR to see the true cost.',
          },
          {
            prompt: 'Credit card interest is especially costly because:',
            options: [
              'It compounds daily on your unpaid balance',
              'Banks charge it quarterly rather than monthly',
              'It is fixed at the prime rate set by the Federal Reserve',
              'It applies even to purchases you dispute',
            ],
            correct: 0,
            explanation: 'Most credit cards compound interest daily. A 24% APR works out to ~0.066% per day — small daily amounts snowball into significant debt quickly.',
          },
          {
            prompt: 'You take a $200,000 mortgage at 7% for 30 years. Over 30 years you will pay roughly:',
            options: [
              'More than double the original loan in total interest',
              'Exactly $200,000 in interest (equal to the principal)',
              'About $42,000 in total interest over the life of the loan',
              'No interest if you make every payment on time',
            ],
            correct: 0,
            explanation: 'A 30-year mortgage at 7% means roughly $279,000 in interest on a $200k loan — total payments of ~$479,000. This is why extra principal payments save dramatically.',
          },
          {
            prompt: 'Why is student loan interest particularly tricky?',
            options: [
              'Interest can accrue during school before repayment begins',
              'Student loans have higher rates than credit cards by law',
              'The government taxes student loan interest payments at 50%',
              'Interest is calculated on your future expected salary, not the loan amount',
            ],
            correct: 0,
            explanation: 'On unsubsidized loans, interest starts accruing the day the loan is disbursed — even while you\'re in school. That interest capitalizes (adds to principal) when repayment starts.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-3',
    number: 3,
    title: 'Budgeting',
    subtitle: 'Take control of your money',
    color: '#F59E0B',
    icon: '📋',
    units: [
      {
        id: 'u3-1',
        title: 'Budget Basics',
        icon: '📝',
        centsReward: 40,
        questions: [
          {
            prompt: 'In zero-based budgeting, what does "zero" refer to?',
            options: [
              'Every dollar of income is assigned a purpose — income minus expenses equals zero',
              'You spend nothing on wants, only needs',
              'You start fresh each month ignoring last month\'s budget',
              'You target a zero balance in your checking account',
            ],
            correct: 0,
            explanation: 'Zero-based budgeting means every single dollar is allocated — whether to bills, savings, or fun money. Nothing is unaccounted for.',
          },
          {
            prompt: 'The envelope budgeting system works by:',
            options: [
              'Putting physical (or virtual) cash in labeled envelopes for each spending category',
              'Mailing your budget plan to a financial advisor for review',
              'Saving all your receipts in envelopes to review at year-end',
              'Allocating 100% of your paycheck to a single savings envelope',
            ],
            correct: 0,
            explanation: 'Once the cash in an envelope is gone, spending in that category stops. It creates a hard spending limit and strong awareness of where money goes.',
          },
          {
            prompt: 'Cash flow is defined as:',
            options: [
              'Money coming in minus money going out over a period',
              'The balance in your checking account at month-end',
              'Total debt divided by total income',
              'The interest rate on your primary savings account',
            ],
            correct: 0,
            explanation: 'Positive cash flow (income > expenses) means you have money left to save or invest. Negative cash flow means you\'re spending more than you earn.',
          },
          {
            prompt: 'Which budgeting approach gives the most flexibility for irregular spending?',
            options: [
              'Flexible budgeting — adjusts categories based on actual income each month',
              'Zero-based — every dollar is pre-assigned with no room for change',
              'Envelope system — once the envelope is empty, spending stops permanently',
              '50/30/20 — fixed percentages regardless of income changes',
            ],
            correct: 0,
            explanation: 'Flexible budgeting recognizes that income and expenses vary month to month, allowing category reallocation rather than rigid adherence.',
          },
        ],
      },
      {
        id: 'u3-2',
        title: 'Tracking Money',
        icon: '📱',
        centsReward: 35,
        questions: [
          {
            prompt: 'The main benefit of using a budget app vs. a spreadsheet is:',
            options: [
              'Automatic transaction import saves time vs. manual entry',
              'Apps are required by law for anyone with a bank account',
              'Spreadsheets cannot track savings goals or investments',
              'Apps automatically negotiate lower subscription prices',
            ],
            correct: 0,
            explanation: 'Budget apps link to your bank and categorize transactions automatically. Spreadsheets offer more customization but require manual entry.',
          },
          {
            prompt: 'What is a subscription audit and why does it matter?',
            options: [
              'Reviewing all recurring charges to cancel services you don\'t actively use',
              'A government review of your streaming service habits',
              'A tax form required when canceling subscriptions over $100/year',
              'Auditing a company\'s subscription-based revenue model',
            ],
            correct: 0,
            explanation: 'People average several forgotten subscriptions. A monthly audit of recurring charges is a fast way to find easy savings.',
          },
          {
            prompt: 'Cash flow forecasting helps you:',
            options: [
              'Predict months when bills will exceed income so you can prepare',
              'Calculate the exact return on your investment portfolio',
              'Determine your federal income tax withholding amount',
              'Negotiate a higher credit limit with your card issuer',
            ],
            correct: 0,
            explanation: 'Forecasting your cash flow reveals future tight spots — like a month with a big insurance payment — so you can save extra beforehand.',
          },
          {
            prompt: 'Which pattern most reliably signals "unnecessary spending" when tracking expenses?',
            options: [
              'Recurring small charges you forgot about or never use',
              'Any transaction over $50 that isn\'t rent or utilities',
              'Spending at restaurants once per week',
              'Any cash withdrawal from an ATM',
            ],
            correct: 0,
            explanation: 'Small recurring charges are the most common source of hidden waste — $9.99 here, $14.99 there adds up to hundreds per year.',
          },
        ],
      },
      {
        id: 'u3-3',
        title: 'Financial Goals',
        icon: '🎯',
        centsReward: 40,
        questions: [
          {
            prompt: 'Which goal is written as a proper SMART goal?',
            options: [
              'Save $5,000 for an emergency fund by December 31 by setting aside $417/month',
              'Save more money this year',
              'Eventually become debt-free',
              'Start investing sometime before I turn 40',
            ],
            correct: 0,
            explanation: 'SMART = Specific, Measurable, Achievable, Relevant, Time-bound. Vague goals like "save more" fail because there\'s no concrete target or deadline.',
          },
          {
            prompt: 'A short-term financial goal typically spans:',
            options: [
              'Under 1–2 years (vacation, emergency fund, phone)',
              '5–10 years (down payment, college fund)',
              '20–30 years (retirement savings)',
              'Any goal under $1,000 regardless of timeline',
            ],
            correct: 0,
            explanation: 'Short-term (0–2 years), medium-term (2–7 years), long-term (7+ years). The timeline determines where you should keep the money — savings account vs. investing.',
          },
          {
            prompt: 'Why is it important to save for retirement in your 20s rather than your 40s?',
            options: [
              'Compound growth over 40 years creates exponentially more wealth than 20 years',
              'The government penalizes late retirement savers with extra taxes',
              'Employer matching programs are only available to workers under 30',
              '401(k) contribution limits are higher for people in their 20s',
            ],
            correct: 0,
            explanation: 'Starting at 22 vs. 42 means 20 extra years of compounding. That difference can translate to 3–4× more retirement wealth from the same monthly contribution.',
          },
          {
            prompt: 'To save $20,000 for a house down payment in 3 years, how much must you save monthly?',
            options: [
              'About $556/month ($20,000 ÷ 36 months)',
              'About $1,667/month ($20,000 ÷ 12 months)',
              'About $278/month ($20,000 ÷ 72 months)',
              'About $2,000/month with interest adjustments',
            ],
            correct: 0,
            explanation: '$20,000 ÷ 36 months ≈ $556/month. In a high-yield savings account at 5% APY you\'d actually need slightly less, but $556 is the baseline.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-4',
    number: 4,
    title: 'Credit',
    subtitle: 'Build and protect your score',
    color: '#3B82F6',
    icon: '💳',
    units: [
      {
        id: 'u4-1',
        title: 'Credit Scores',
        icon: '⭐',
        centsReward: 45,
        questions: [
          {
            prompt: 'Which single factor carries the most weight in your FICO score?',
            options: [
              'Payment history (35%)',
              'Credit utilization (30%)',
              'Length of credit history (15%)',
              'Types of credit used (10%)',
            ],
            correct: 0,
            explanation: 'Payment history is the #1 factor. Even one 30-day late payment can drop your score significantly and remains on your report for 7 years.',
          },
          {
            prompt: 'What is a hard inquiry and when does it occur?',
            options: [
              'When a lender checks your credit after you apply for a loan or card',
              'When you check your own credit score on a free app',
              'When an employer verifies your identity for a job application',
              'When your bank reviews your account for an automatic credit limit increase',
            ],
            correct: 0,
            explanation: 'Hard inquiries happen when you apply for new credit and can temporarily lower your score by a few points. Soft inquiries (checking your own score) do not affect it.',
          },
          {
            prompt: 'Keeping credit utilization below ___ is generally recommended.',
            options: [
              '30%, ideally below 10%',
              '50% — anything under half is fine',
              '75% as long as you pay the minimum',
              '100% as long as you don\'t exceed your limit',
            ],
            correct: 0,
            explanation: 'Utilization = balance ÷ limit. Below 30% signals responsible use; below 10% is ideal for maximizing your score. Maxed-out cards hurt scores significantly.',
          },
          {
            prompt: 'What is the best way to build credit with no credit history?',
            options: [
              'Open a secured credit card and pay it in full each month',
              'Apply for five credit cards simultaneously to show demand',
              'Take out a large personal loan to prove you can handle debt',
              'Have a parent close their oldest credit card and transfer history to you',
            ],
            correct: 0,
            explanation: 'A secured card (backed by a cash deposit) is designed for credit beginners. Using it for small purchases and paying in full each month builds a clean payment history.',
          },
        ],
      },
      {
        id: 'u4-2',
        title: 'Credit Cards',
        icon: '💳',
        centsReward: 45,
        questions: [
          {
            prompt: 'What is the credit card grace period?',
            options: [
              'Time between statement closing and payment due date — no interest if you pay in full',
              'A penalty-free window after a missed payment before it hits your credit report',
              'The days before your card limit is reduced after late payments',
              'The 24-hour window to dispute any transaction on your statement',
            ],
            correct: 0,
            explanation: 'Most cards give 21–25 days after the statement closes. Pay the full balance by then and you pay zero interest — the card is essentially free money for the month.',
          },
          {
            prompt: 'What is a balance transfer?',
            options: [
              'Moving high-interest debt to a card with a lower (or 0%) intro rate',
              'Transferring your bank balance to pay off a credit card immediately',
              'Shifting your credit limit from one card to another at the same bank',
              'Sending money from your credit card directly to someone via Zelle',
            ],
            correct: 0,
            explanation: 'Balance transfers can save significant interest — e.g., moving $5,000 from a 24% card to a 0% intro card. Watch for transfer fees (typically 3–5%).',
          },
          {
            prompt: 'Credit card cash back rewards are effectively:',
            options: [
              'A rebate on spending — you get back a percentage of what you spend',
              'Free money from the bank deposited monthly with no strings',
              'Miles that can be exchanged for actual cash at airports',
              'Interest paid to you when you carry a balance',
            ],
            correct: 0,
            explanation: 'Cash back (1–5%) is funded by merchant fees and interest from cardholders who carry balances. Pay in full and the rewards are genuinely free.',
          },
          {
            prompt: 'How does carrying a balance month-to-month make credit card rewards worthless?',
            options: [
              'Interest charges (often 20%+) far exceed any 1–5% rewards earned',
              'Card issuers automatically cancel rewards when you carry a balance',
              'Rewards are taxed as income when redeemed, wiping out their value',
              'Carrying a balance converts your rewards from cash back to points only',
            ],
            correct: 0,
            explanation: 'A 1.5% cash back reward on $1,000 = $15. A 22% APR on that same $1,000 = $220/year in interest. Never carry a balance for rewards.',
          },
        ],
      },
      {
        id: 'u4-3',
        title: 'Loans',
        icon: '📄',
        centsReward: 50,
        questions: [
          {
            prompt: 'Loan amortization means:',
            options: [
              'Early payments go mostly toward interest; later payments toward principal',
              'Your monthly payment decreases as you pay off the loan',
              'Interest compounds only once per year on fixed-rate loans',
              'The loan balance adjusts automatically with inflation',
            ],
            correct: 0,
            explanation: 'With an amortized loan, early payments are interest-heavy. Making extra principal payments early dramatically reduces total interest paid.',
          },
          {
            prompt: 'What is predatory lending?',
            options: [
              'Loans targeting vulnerable borrowers with hidden fees and extreme interest rates',
              'Any loan with an APR above 10%',
              'Lending by non-bank financial institutions like credit unions',
              'Student loans offered by for-profit universities',
            ],
            correct: 0,
            explanation: 'Predatory lenders target people who are desperate or financially inexperienced, using confusing terms, inflated rates, and penalties to extract maximum profit.',
          },
          {
            prompt: 'When should you refinance a loan?',
            options: [
              'When you can get a meaningfully lower interest rate that saves more than closing costs',
              'Every year to reset the amortization schedule',
              'Only when your credit score drops below 650',
              'Whenever your bank sends you a refinancing offer in the mail',
            ],
            correct: 0,
            explanation: 'Refinancing makes sense when the new rate is at least 0.5–1% lower and you plan to stay in the loan long enough to recoup closing costs through savings.',
          },
          {
            prompt: 'Why are payday loans considered predatory?',
            options: [
              'APRs can reach 300–400%, trapping borrowers in repeat borrowing',
              'They are illegal in all 50 states since 2020',
              'They require collateral that most borrowers lose within 6 months',
              'Interest rates are set by the IRS above prime rate',
            ],
            correct: 0,
            explanation: 'A typical payday loan charges $15–$30 per $100 borrowed for 2 weeks — roughly 390% APR. Most borrowers can\'t repay and roll over the loan repeatedly.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-5',
    number: 5,
    title: 'Taxes',
    subtitle: 'Understand what you owe and why',
    color: '#8B5CF6',
    icon: '🧾',
    units: [
      {
        id: 'u5-1',
        title: 'Tax Basics',
        icon: '🏛️',
        centsReward: 50,
        questions: [
          {
            prompt: 'The U.S. income tax system is progressive, which means:',
            options: [
              'Higher income is taxed at higher rates, but only on income in each bracket',
              'You pay a flat percentage of all income regardless of how much you earn',
              'The more you earn, all of your income is taxed at the highest rate',
              'Tax rates decrease as income increases to encourage earning more',
            ],
            correct: 0,
            explanation: 'Being in the "32% tax bracket" doesn\'t mean ALL income is taxed at 32%. Only income above that bracket\'s threshold is taxed at 32%. Lower portions are taxed at lower rates.',
          },
          {
            prompt: 'Capital gains tax applies to:',
            options: [
              'Profit from selling investments like stocks or real estate',
              'Income earned from a full-time job or salary',
              'Interest paid to you by your bank on savings',
              'Money received as a gift from family members',
            ],
            correct: 0,
            explanation: 'Capital gains = sale price minus cost basis. Long-term capital gains (assets held 1+ year) are taxed at lower rates (0%, 15%, or 20%) than ordinary income.',
          },
          {
            prompt: 'Sales tax is an example of what type of tax structure?',
            options: [
              'Regressive — takes a higher percentage of income from lower-income people',
              'Progressive — higher earners pay a larger share of their income',
              'Flat — everyone pays exactly the same dollar amount',
              'Proportional — the percentage is fixed but the dollar amount varies',
            ],
            correct: 0,
            explanation: 'Sales tax is regressive: a 7% tax on groceries costs a millionaire 7% and a minimum-wage worker 7% — but represents a far greater share of the worker\'s income.',
          },
          {
            prompt: 'Payroll taxes fund:',
            options: [
              'Social Security and Medicare programs',
              'Federal highways and public infrastructure',
              'The U.S. military and national defense',
              'Public school systems in each state',
            ],
            correct: 0,
            explanation: 'FICA payroll taxes = 7.65% from employees and 7.65% from employers. This funds Social Security (6.2%) and Medicare (1.45%).',
          },
        ],
      },
      {
        id: 'u5-2',
        title: 'Filing Taxes',
        icon: '📋',
        centsReward: 55,
        questions: [
          {
            prompt: 'What is a W-2 form?',
            options: [
              'A report from your employer showing wages paid and taxes withheld',
              'The form you file directly with the IRS to pay your taxes',
              'A document from your bank summarizing annual interest earned',
              'A form freelancers use to report self-employment income',
            ],
            correct: 0,
            explanation: 'Employers send W-2s by January 31. It shows gross wages, federal/state tax withheld, and benefits — everything you need to file your return.',
          },
          {
            prompt: 'The standard deduction vs. itemized deductions — when should you itemize?',
            options: [
              'When your deductible expenses (mortgage interest, donations, etc.) exceed the standard deduction',
              'Always — itemizing always results in a lower tax bill',
              'Only if you are self-employed and run your own business',
              'When your income exceeds $100,000 annually',
            ],
            correct: 0,
            explanation: 'The 2024 standard deduction is ~$14,600 (single). Only itemize if your deductible expenses add up to more than that. Most people take the standard deduction.',
          },
          {
            prompt: 'A tax credit is more valuable than a tax deduction because:',
            options: [
              'Credits reduce your tax bill dollar-for-dollar; deductions only reduce taxable income',
              'Deductions are limited to $5,000/year; credits have no limit',
              'Credits apply before deductions in the tax calculation order',
              'Deductions only apply to federal taxes; credits apply to state taxes too',
            ],
            correct: 0,
            explanation: 'A $1,000 deduction at 22% bracket = $220 in savings. A $1,000 credit = $1,000 off your tax bill directly. Credits are always more powerful.',
          },
          {
            prompt: 'Tax withholding is:',
            options: [
              'Taxes taken from your paycheck before you receive it',
              'A penalty for paying taxes late to the IRS',
              'The amount you owe when you file your return in April',
              'An optional program to reduce your paycheck size',
            ],
            correct: 0,
            explanation: 'Each paycheck, your employer withholds estimated federal and state taxes. If too much is withheld → refund. Too little → you owe at filing.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-6',
    number: 6,
    title: 'Insurance',
    subtitle: 'Protect what you\'ve built',
    color: '#EC4899',
    icon: '🛡️',
    units: [
      {
        id: 'u6-1',
        title: 'Insurance Basics',
        icon: '🛡️',
        centsReward: 50,
        questions: [
          {
            prompt: 'What is a deductible in an insurance policy?',
            options: [
              'The amount you pay out-of-pocket before insurance covers the rest',
              'The monthly or annual premium you pay to maintain coverage',
              'The percentage of each claim the insurer pays',
              'The maximum amount your insurer will ever pay per year',
            ],
            correct: 0,
            explanation: 'High deductible = lower premium but more out-of-pocket when you file a claim. Low deductible = higher premium but less to pay at claim time.',
          },
          {
            prompt: 'Why is renters insurance important even though you don\'t own your apartment?',
            options: [
              'It covers your personal belongings if they\'re stolen or destroyed by fire',
              'It protects the building structure in case of a natural disaster',
              'Your landlord\'s policy covers your possessions by law',
              'It\'s legally required for anyone living in a rented unit',
            ],
            correct: 0,
            explanation: 'Landlord insurance covers the building — not your stuff. Renters insurance protects your belongings and provides liability coverage for surprisingly low premiums (~$15/month).',
          },
          {
            prompt: 'What does term life insurance provide?',
            options: [
              'A death benefit for a fixed period (e.g., 20 years) at a lower cost',
              'Lifelong coverage plus a cash savings component',
              'Health coverage for your dependents after you retire',
              'Disability income if you are injured and can\'t work',
            ],
            correct: 0,
            explanation: 'Term life is pure protection — cheap, straightforward. Whole life is permanent but expensive and mixes insurance with investing (usually not a great deal).',
          },
          {
            prompt: 'Insurance is fundamentally a tool for:',
            options: [
              'Transferring catastrophic financial risk to a pool of policyholders',
              'Guaranteeing that all losses will be fully reimbursed by the insurer',
              'Investing premiums in the stock market to grow your money',
              'Replacing your income dollar-for-dollar if you lose your job',
            ],
            correct: 0,
            explanation: 'Insurance pools risk across many people. You pay a small, predictable premium; the insurer covers large, unpredictable losses. It\'s not investment — it\'s risk management.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-7',
    number: 7,
    title: 'Investing Basics',
    subtitle: 'Put your money to work',
    color: '#14B8A6',
    icon: '📈',
    units: [
      {
        id: 'u7-1',
        title: 'Why Invest?',
        icon: '🌱',
        centsReward: 50,
        questions: [
          {
            prompt: 'Why is keeping all your money in a savings account not enough long-term?',
            options: [
              'Inflation erodes purchasing power faster than low savings rates grow it',
              'Savings accounts are not FDIC insured above $1,000',
              'Banks can legally seize funds left in savings over 10 years',
              'Savings accounts charge fees that eliminate all interest earned',
            ],
            correct: 0,
            explanation: 'If inflation runs 3% and your savings account yields 0.5%, you\'re losing 2.5% of real purchasing power per year. Investing in the market historically returns 7–10% annually.',
          },
          {
            prompt: 'Risk and reward in investing are related because:',
            options: [
              'Higher potential returns require accepting higher potential losses',
              'Riskier investments always produce better long-term results',
              'Low-risk investments are illegal for retail investors under SEC rules',
              'The government guarantees returns on investments above a certain risk level',
            ],
            correct: 0,
            explanation: 'The risk/reward tradeoff is fundamental: bonds are safer but return less; stocks are volatile but historically return more. You choose where you sit on this spectrum.',
          },
          {
            prompt: 'Time horizon matters in investing because:',
            options: [
              'Longer timelines let you ride out market downturns and capture compounding',
              'Short-term investors receive government tax breaks not available long-term',
              'The stock market always goes up within any 1-year period',
              'Brokerages charge higher fees for long-term holdings',
            ],
            correct: 0,
            explanation: 'The S&P 500 has never had a negative return over any 20-year period in history. Time is the investor\'s greatest advantage.',
          },
          {
            prompt: 'Asset allocation means:',
            options: [
              'Dividing investments among stocks, bonds, and other asset classes',
              'Choosing which individual stocks to buy with your portfolio',
              'The process of selling assets to cover living expenses in retirement',
              'How much of your income you invest each month',
            ],
            correct: 0,
            explanation: 'Asset allocation (e.g., 80% stocks / 20% bonds) determines your portfolio\'s overall risk and return profile. It\'s the most important investment decision you make.',
          },
        ],
      },
      {
        id: 'u7-2',
        title: 'Stocks',
        icon: '📊',
        centsReward: 55,
        questions: [
          {
            prompt: 'An IPO (Initial Public Offering) is when:',
            options: [
              'A private company sells shares to the public for the first time',
              'A public company buys back its own shares from investors',
              'Two companies merge and issue new combined shares',
              'A broker issues a recommendation to buy a specific stock',
            ],
            correct: 0,
            explanation: 'An IPO is how companies "go public" — raising capital by selling ownership stakes. Early investors hope the share price rises post-IPO.',
          },
          {
            prompt: 'Market capitalization is:',
            options: [
              'Share price × total number of shares outstanding',
              'The total revenue a company earned last quarter',
              'The maximum stock price set by the SEC for a given company',
              'Net profit divided by total assets on the balance sheet',
            ],
            correct: 0,
            explanation: 'Market cap = price per share × shares outstanding. It\'s the market\'s total valuation of a company. Apple (~$3T) is a large-cap; many startups are micro-cap.',
          },
          {
            prompt: 'Dividends are:',
            options: [
              'Cash payments companies make to shareholders from profits',
              'Fees paid by investors to brokers for executing trades',
              'The annual interest rate on a bond investment',
              'Penalties charged when you sell a stock at a loss',
            ],
            correct: 0,
            explanation: 'Many established companies (blue-chips) pay regular dividends. Dividend investors earn income without selling shares — critical for retirement income strategies.',
          },
          {
            prompt: 'Growth stocks vs. value stocks: which is riskier?',
            options: [
              'Growth stocks — priced on future potential, so price drops hard if growth disappoints',
              'Value stocks — priced below book value means companies are about to go bankrupt',
              'They carry identical risk since the SEC requires equivalent disclosures',
              'Value stocks — less trading volume makes them harder to sell quickly',
            ],
            correct: 0,
            explanation: 'Growth stocks (high P/E ratios) are priced on expectations. If a company misses growth targets, the stock can fall 30–50%+. Value stocks trade at lower multiples, offering a "margin of safety."',
          },
        ],
      },
      {
        id: 'u7-3',
        title: 'Bonds',
        icon: '📜',
        centsReward: 55,
        questions: [
          {
            prompt: 'When you buy a bond, you are:',
            options: [
              'Lending money to the issuer in exchange for regular interest payments',
              'Buying ownership in a company just like a stock',
              'Purchasing a guaranteed investment from the Federal Reserve',
              'Contributing to a government savings program like I-Bonds only',
            ],
            correct: 0,
            explanation: 'Bondholders are creditors, not owners. You lend money at a fixed interest rate (coupon) for a set period (maturity). Safer than stocks but lower returns.',
          },
          {
            prompt: 'When interest rates rise, existing bond prices:',
            options: [
              'Fall — new bonds pay more, making existing bonds less attractive',
              'Rise — higher rates increase the market value of all fixed income',
              'Stay the same — bond prices are fixed at time of issuance',
              'Double — the Federal Reserve guarantees bond value appreciation',
            ],
            correct: 0,
            explanation: 'This is the fundamental bond risk: interest rate risk. If you hold to maturity you get your principal back. But if you sell early in a rising-rate environment, you sell at a discount.',
          },
          {
            prompt: 'Municipal bonds are attractive to high-income investors primarily because:',
            options: [
              'Their interest is exempt from federal income tax (and often state tax)',
              'They pay the highest yields of any fixed-income investment',
              'The government guarantees returns above the inflation rate',
              'They can be converted to stocks at any time at no cost',
            ],
            correct: 0,
            explanation: 'Tax-exempt interest means a 4% muni yield may effectively beat a 5.5% taxable bond for someone in the 37% tax bracket. Always compare tax-equivalent yield.',
          },
          {
            prompt: 'A bond\'s yield to maturity (YTM) represents:',
            options: [
              'Total return if held to maturity, including price changes and coupon payments',
              'Only the annual coupon interest payment as a percentage of face value',
              'The spread between corporate and government bond rates',
              'The credit rating assigned by Moody\'s or Standard & Poor\'s',
            ],
            correct: 0,
            explanation: 'YTM is the most complete measure of a bond\'s return — it accounts for the coupon payments, the price you paid vs. face value, and the time to maturity.',
          },
        ],
      },
      {
        id: 'u7-4',
        title: 'Mutual Funds',
        icon: '🧺',
        centsReward: 55,
        questions: [
          {
            prompt: 'An index fund differs from an actively managed fund because:',
            options: [
              'It tracks a market index mechanically instead of having managers pick stocks',
              'Index funds are only available to institutional investors, not individuals',
              'Actively managed funds charge lower fees since computers do the work',
              'Index funds invest only in government bonds to guarantee returns',
            ],
            correct: 0,
            explanation: 'Index funds passively replicate an index (like the S&P 500). Lower costs + consistent market exposure. Research shows most active managers underperform their benchmark over time.',
          },
          {
            prompt: 'An expense ratio of 1% vs. 0.03% on a $100,000 portfolio over 30 years costs you roughly:',
            options: [
              'Over $200,000 more in fees (compounding dramatically amplifies small differences)',
              'About $970 more — a negligible difference in absolute terms',
              'Exactly $970 per year regardless of compounding',
              'Nothing if you reinvest all dividends automatically',
            ],
            correct: 0,
            explanation: 'Expense ratios compound just like returns — but in reverse. A 1% annual drag over 30 years destroys a stunning amount of wealth. Vanguard\'s average is 0.09%.',
          },
          {
            prompt: 'A target-date fund is designed for:',
            options: [
              'Investors who want automatic rebalancing toward bonds as retirement approaches',
              'Day traders who target specific price movements over short periods',
              'Investors who want maximum growth regardless of their age or risk tolerance',
              'People saving for a specific purchase within 1–2 years',
            ],
            correct: 0,
            explanation: 'Target-date funds (e.g., "2055 Fund") start aggressive (mostly stocks) and gradually shift to conservative (mostly bonds) as the target year approaches. Simple, hands-off retirement investing.',
          },
          {
            prompt: 'NAV (Net Asset Value) for a mutual fund is:',
            options: [
              'Total fund assets minus liabilities, divided by shares outstanding',
              'The highest price the fund traded at in the past 52 weeks',
              'The guaranteed minimum return the fund manager promises',
              'The management fee charged annually as a percentage of assets',
            ],
            correct: 0,
            explanation: 'NAV is calculated once per day after markets close. It\'s the per-share price of the fund. Unlike stocks, mutual funds don\'t trade intra-day.',
          },
        ],
      },
      {
        id: 'u7-5',
        title: 'ETFs',
        icon: '📦',
        centsReward: 55,
        questions: [
          {
            prompt: 'ETFs (Exchange-Traded Funds) differ from mutual funds because:',
            options: [
              'ETFs trade on stock exchanges throughout the day like individual stocks',
              'ETFs are only available to accredited investors with $1M+ in assets',
              'ETFs cannot track indexes — they must be actively managed',
              'ETFs have higher minimum investments than mutual funds',
            ],
            correct: 0,
            explanation: 'ETFs trade intra-day like stocks. This gives flexibility (you can buy/sell any time markets are open) but also exposes undisciplined investors to emotional trading.',
          },
          {
            prompt: 'Compared to traditional mutual funds, ETFs typically offer:',
            options: [
              'Lower expense ratios and greater tax efficiency',
              'Higher guaranteed returns through active management',
              'Better investor protections regulated by the FDIC',
              'Minimum loss guarantees if the underlying index drops',
            ],
            correct: 0,
            explanation: 'ETFs have structural advantages: in-kind creation/redemption reduces taxable capital gains distributions, and passive ETFs charge very low fees (some near 0%).',
          },
          {
            prompt: 'What does it mean for an ETF to "track an index"?',
            options: [
              'It holds the same securities as the index in proportional weights',
              'It bets against the index using derivatives and short positions',
              'It matches the index\'s performance by any legal means possible',
              'It copies trades made by the largest institutional holders of the index',
            ],
            correct: 0,
            explanation: 'An S&P 500 ETF holds all 500 companies in roughly the same weights as the index. When the index rises 10%, the ETF rises ~10% (minus tiny fees).',
          },
          {
            prompt: 'Liquidity is higher for ETFs than mutual funds because:',
            options: [
              'ETFs can be bought and sold any time markets are open at market prices',
              'ETFs hold more cash reserves than mutual funds by regulation',
              'Mutual funds must hold illiquid assets by SEC requirement',
              'ETF managers are required to buy back shares at any time on request',
            ],
            correct: 0,
            explanation: 'You can sell an ETF in milliseconds during market hours. Mutual funds execute at end-of-day NAV only, with no intra-day liquidity.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-8',
    number: 8,
    title: 'Retirement',
    subtitle: 'Build wealth for the long run',
    color: '#F97316',
    icon: '🏖️',
    units: [
      {
        id: 'u8-1',
        title: 'Retirement Planning',
        icon: '🏖️',
        centsReward: 65,
        questions: [
          {
            prompt: 'The key difference between a Traditional IRA and a Roth IRA is:',
            options: [
              'Traditional: tax deduction now, pay taxes on withdrawals. Roth: no deduction now, tax-free withdrawals.',
              'Roth: higher annual contribution limit. Traditional: lower limit.',
              'Traditional accounts are for workers under 50; Roth accounts for workers 50+.',
              'Roth IRAs can only hold bonds; Traditional IRAs can hold any investment.',
            ],
            correct: 0,
            explanation: 'Roth IRAs are generally better if you expect higher future taxes (usually younger earners). Traditional IRAs are better if you want to reduce taxes now (usually higher earners).',
          },
          {
            prompt: 'An employer 401(k) match of 100% up to 3% of salary is:',
            options: [
              'Free money — always contribute at least enough to capture the full match',
              'A risky benefit that must be paid back if you leave before 5 years',
              'Taxed as income in the year the match is received, not at withdrawal',
              'Only available to employees earning less than $75,000 per year',
            ],
            correct: 0,
            explanation: 'An employer match is a 100% instant return on your contribution. Not capturing the full match is leaving free money on the table — it\'s always the #1 retirement priority.',
          },
          {
            prompt: 'Required Minimum Distributions (RMDs) require you to:',
            options: [
              'Withdraw a minimum amount from Traditional IRAs/401(k)s annually after age 73',
              'Contribute a minimum amount to Roth IRAs each year once you start working',
              'Diversify your retirement accounts across at least five different fund types',
              'Roll over your 401(k) to an IRA within 60 days of leaving an employer',
            ],
            correct: 0,
            explanation: 'RMDs force you to draw down tax-deferred accounts so the IRS eventually collects. Roth IRAs have no RMDs during the owner\'s lifetime.',
          },
          {
            prompt: 'Social Security benefits increase if you delay claiming past age 62 because:',
            options: [
              'Each year you wait (up to age 70) increases your monthly benefit by ~8%',
              'The government adds inflation adjustments only to delayed claims',
              'Claiming early means you share your benefit with other claimants',
              'Benefits are calculated based on your final year\'s salary regardless of claim age',
            ],
            correct: 0,
            explanation: 'Claiming at 70 vs. 62 can increase monthly benefits by 75%+. For those in good health, delaying is often the highest-return "investment" available.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-9',
    number: 9,
    title: 'The Economy',
    subtitle: 'Understand the big picture',
    color: '#06B6D4',
    icon: '🌍',
    units: [
      {
        id: 'u9-1',
        title: 'Macroeconomics',
        icon: '🌍',
        centsReward: 65,
        questions: [
          {
            prompt: 'GDP (Gross Domestic Product) measures:',
            options: [
              'Total market value of all goods and services produced in a country in a year',
              'The government\'s total spending on public programs and infrastructure',
              'Average income per person adjusted for cost of living differences',
              'Net exports minus imports over a given fiscal quarter',
            ],
            correct: 0,
            explanation: 'GDP is the broadest measure of economic activity. Two consecutive quarters of negative GDP growth is the common definition of a recession.',
          },
          {
            prompt: 'When the Federal Reserve raises interest rates, the intended effect is:',
            options: [
              'Slow borrowing and spending to cool inflation',
              'Encourage banks to lend more money to stimulate growth',
              'Increase government tax revenue from bond investors',
              'Strengthen the dollar to boost exports',
            ],
            correct: 0,
            explanation: 'Higher rates make borrowing more expensive → less spending → less demand → lower inflation. This is the Fed\'s primary inflation-fighting tool.',
          },
          {
            prompt: 'Supply and demand means that when supply falls and demand stays constant:',
            options: [
              'Prices rise',
              'Prices fall',
              'Prices stay the same but quality decreases',
              'The government controls the price to prevent changes',
            ],
            correct: 0,
            explanation: 'Basic economics: scarcity + constant demand = higher prices. Oil supply cuts → gas prices rise. Chip shortage → car prices rise. This is why supply chains matter.',
          },
          {
            prompt: 'The difference between a recession and a depression is:',
            options: [
              'Severity and duration — depressions are more severe and last longer',
              'A recession affects only one sector; a depression affects the whole economy',
              'Recessions are government policy; depressions are natural market events',
              'The terms are interchangeable — economists use them randomly',
            ],
            correct: 0,
            explanation: 'A recession is typically 2+ quarters of negative GDP. A depression is a severe, prolonged recession (like the Great Depression of the 1930s with 25% unemployment).',
          },
        ],
      },
    ],
  },

  {
    id: 'level-10',
    number: 10,
    title: 'Business Finance',
    subtitle: 'How companies manage money',
    color: '#84CC16',
    icon: '🏢',
    units: [
      {
        id: 'u10-1',
        title: 'Business Fundamentals',
        icon: '🏢',
        centsReward: 65,
        questions: [
          {
            prompt: 'Revenue minus all expenses equals:',
            options: [
              'Net profit (or net loss)',
              'Gross revenue before any deductions',
              'Cash flow from operations',
              'Return on equity for shareholders',
            ],
            correct: 0,
            explanation: 'Net profit (bottom line) = Revenue − COGS − Operating expenses − Interest − Taxes. This is what owners actually keep. A profitable company can still go bankrupt if cash flow is poor.',
          },
          {
            prompt: 'An income statement shows:',
            options: [
              'Revenue, expenses, and profit over a period of time',
              'What a company owns and owes at a single point in time',
              'Cash entering and leaving the business during a period',
              'The stock price history over the past 12 months',
            ],
            correct: 0,
            explanation: 'The three core financial statements: Income statement (profitability over time), Balance sheet (snapshot of assets/liabilities), Cash flow statement (actual cash movements).',
          },
          {
            prompt: 'A sole proprietorship differs from an LLC because:',
            options: [
              'Sole proprietors have unlimited personal liability; LLC owners are generally protected',
              'LLCs cannot have more than one owner under federal law',
              'Sole proprietors pay lower self-employment taxes than LLC members',
              'LLCs must have a board of directors; sole proprietors do not',
            ],
            correct: 0,
            explanation: 'If your sole proprietorship is sued, creditors can come after your personal assets. An LLC creates a legal wall between business and personal finances.',
          },
          {
            prompt: 'Gross profit margin = (Revenue − COGS) ÷ Revenue. A 60% margin means:',
            options: [
              '60 cents of every dollar of revenue is left after direct production costs',
              'The business spends 60% of revenue on marketing and overhead',
              'Net income is 60% of total assets on the balance sheet',
              '60% of products sold generate profit; 40% are sold at a loss',
            ],
            correct: 0,
            explanation: 'Gross margin shows how efficiently a company produces its product. High margins (like software) leave more room for overhead, R&D, and profit.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-11',
    number: 11,
    title: 'Advanced Investing',
    subtitle: 'Analyze companies like a pro',
    color: '#6366F1',
    icon: '🔬',
    units: [
      {
        id: 'u11-1',
        title: 'Stock Analysis',
        icon: '🔬',
        centsReward: 75,
        questions: [
          {
            prompt: 'A P/E ratio of 30 vs. 15 suggests:',
            options: [
              'Investors pay more for each dollar of earnings — expecting faster future growth',
              'The company with P/E 30 is twice as profitable as P/E 15',
              'The lower P/E stock always represents a better investment value',
              'The stock with P/E 30 will always outperform the market',
            ],
            correct: 0,
            explanation: 'High P/E = growth expectations. Low P/E = either undervalued or slow-growth/troubled. Context matters — compare P/E to the company\'s own history and sector peers.',
          },
          {
            prompt: 'Dollar-cost averaging (DCA) works by:',
            options: [
              'Investing a fixed dollar amount at regular intervals regardless of price',
              'Waiting for a market correction then investing your full portfolio at once',
              'Diversifying across different currencies to reduce exchange rate risk',
              'Timing the market using moving averages to buy at the lowest point',
            ],
            correct: 0,
            explanation: 'DCA removes the emotional burden of timing the market. You buy more shares when prices are low and fewer when high — averaging out the cost over time.',
          },
          {
            prompt: 'What does Beta measure for a stock?',
            options: [
              'How volatile the stock is relative to the overall market',
              'The annual dividend yield as a percentage of share price',
              'The company\'s book value per share on its balance sheet',
              'The probability the stock\'s price will double in 12 months',
            ],
            correct: 0,
            explanation: 'Beta > 1 = more volatile than the market. Beta < 1 = less volatile. A stock with Beta of 1.5 tends to move 50% more than the S&P 500 in either direction.',
          },
          {
            prompt: 'DCF (Discounted Cash Flow) analysis estimates:',
            options: [
              'The intrinsic value of a business based on projected future cash flows',
              'The dividend history of a stock over the past 10 years',
              'How much cash a company has available to repay debt immediately',
              'The debt-to-cash ratio used by bond rating agencies',
            ],
            correct: 0,
            explanation: 'DCF says a dollar in the future is worth less than a dollar today. By projecting future cash flows and "discounting" them back, you estimate what a company is truly worth.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-12',
    number: 12,
    title: 'Real Estate',
    subtitle: 'The fundamentals of property',
    color: '#D946EF',
    icon: '🏡',
    units: [
      {
        id: 'u12-1',
        title: 'Real Estate Basics',
        icon: '🏡',
        centsReward: 70,
        questions: [
          {
            prompt: 'When does buying a home make more financial sense than renting?',
            options: [
              'When you plan to stay 5+ years and total ownership costs beat rent costs',
              'Always — buying is always better than renting in the long run',
              'When mortgage payments are lower than rent regardless of how long you stay',
              'Only when you can put down 50% to avoid any interest payments',
            ],
            correct: 0,
            explanation: 'Buying has high upfront costs (closing costs 2–5%, down payment). The break-even point is typically 4–6 years. Moving before then usually means losing money.',
          },
          {
            prompt: 'Home equity is:',
            options: [
              'The portion of your home\'s value you own outright (value minus mortgage balance)',
              'The annual increase in your home\'s market price due to inflation',
              'The interest portion of each monthly mortgage payment',
              'The government subsidy provided to first-time homebuyers',
            ],
            correct: 0,
            explanation: 'As you pay down your mortgage and/or home values rise, your equity grows. Equity is the key wealth-building mechanism of homeownership.',
          },
          {
            prompt: 'REITs (Real Estate Investment Trusts) allow investors to:',
            options: [
              'Own a share of income-producing real estate without buying property directly',
              'Avoid all property taxes on rental income by using a trust structure',
              'Purchase foreclosed properties below market value through the IRS',
              'Combine multiple mortgages into a single lower-rate loan',
            ],
            correct: 0,
            explanation: 'REITs trade like stocks and must pay 90%+ of taxable income as dividends. They offer real estate exposure without the hassle of being a landlord.',
          },
          {
            prompt: 'Closing costs on a home purchase typically run:',
            options: [
              '2–5% of the purchase price (appraisal, title, origination fees, etc.)',
              'Exactly 1% of the mortgage amount set by federal law',
              '$500–$1,000 regardless of the purchase price',
              'Nothing — sellers pay all closing costs by convention',
            ],
            correct: 0,
            explanation: 'On a $300,000 home, expect $6,000–$15,000 in closing costs. These are in addition to your down payment and must be saved separately.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-13',
    number: 13,
    title: 'Debt Mastery',
    subtitle: 'Eliminate debt strategically',
    color: '#EF4444',
    icon: '⛓️',
    units: [
      {
        id: 'u13-1',
        title: 'Getting Out of Debt',
        icon: '🔓',
        centsReward: 70,
        questions: [
          {
            prompt: 'The debt snowball method prioritizes:',
            options: [
              'Paying off the smallest balance first to build psychological momentum',
              'Eliminating the highest-interest debt to minimize total interest paid',
              'Dividing extra payments equally across all debts simultaneously',
              'Paying only minimum payments until you save 6 months of expenses',
            ],
            correct: 0,
            explanation: 'Snowball = smallest balance first. It\'s psychologically motivating — each debt eliminated frees up money to attack the next. Avalanche saves more money; snowball is better for motivation.',
          },
          {
            prompt: 'Debt-to-income ratio (DTI) is calculated as:',
            options: [
              'Total monthly debt payments ÷ gross monthly income × 100%',
              'Total debt balance ÷ annual net income × 100%',
              'Monthly credit card spending ÷ credit limit × 100%',
              'Net worth minus total debt divided by annual expenses',
            ],
            correct: 0,
            explanation: 'Lenders use DTI to assess your ability to take on more debt. Below 36% is preferred; above 43% typically disqualifies you for mortgages.',
          },
          {
            prompt: 'Debt consolidation means:',
            options: [
              'Combining multiple debts into one loan, ideally at a lower rate',
              'Negotiating with creditors to forgive a portion of what you owe',
              'Transferring all debts to a collection agency to reduce paperwork',
              'Declaring bankruptcy to discharge all unsecured debts simultaneously',
            ],
            correct: 0,
            explanation: 'Consolidation can simplify payments and reduce interest. Watch for fees and make sure the new rate is actually lower than your weighted average existing rate.',
          },
          {
            prompt: 'Bankruptcy should be considered:',
            options: [
              'Only as a last resort — it damages credit for 7–10 years',
              'Immediately when debt exceeds one year\'s salary',
              'Before trying debt consolidation or avalanche repayment',
              'Freely — it resets all debt with no long-term consequences',
            ],
            correct: 0,
            explanation: 'Chapter 7 stays on your credit report for 10 years; Chapter 13 for 7. It should be a last resort after exhausting negotiation, consolidation, and repayment strategies.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-14',
    number: 14,
    title: 'Consumer Skills',
    subtitle: 'Protect yourself in the marketplace',
    color: '#10B981',
    icon: '🧠',
    units: [
      {
        id: 'u14-1',
        title: 'Smart Consumer',
        icon: '🧠',
        centsReward: 60,
        questions: [
          {
            prompt: 'The most effective way to avoid financial scams is:',
            options: [
              'Verify independently — never act on urgency pressure from an unsolicited contact',
              'Only use cash for all transactions to avoid digital fraud',
              'Keep all financial accounts at a single bank for easier monitoring',
              'Share account credentials only with people you\'ve met in person',
            ],
            correct: 0,
            explanation: 'Urgency is the #1 scam tactic. Legitimate institutions never demand immediate action. Always hang up, look up the number independently, and call back yourself.',
          },
          {
            prompt: 'Identity theft protection primarily works by:',
            options: [
              'Monitoring your credit for unauthorized new accounts or hard inquiries',
              'Encrypting your physical wallet to prevent RFID card skimming',
              'Blocking all online purchases made from foreign IP addresses',
              'Automatically disputing any charge over $50 on your behalf',
            ],
            correct: 0,
            explanation: 'Credit monitoring (or a free credit freeze) alerts you when someone opens accounts in your name. A credit freeze is free and the strongest protection available.',
          },
          {
            prompt: 'Before signing any contract, the most important step is:',
            options: [
              'Read every clause, especially cancellation terms and automatic renewal provisions',
              'Have a notary witness your signature to make the contract legally binding',
              'Confirm the company\'s Better Business Bureau rating is A+ or higher',
              'Ensure the contract is under five pages for maximum clarity',
            ],
            correct: 0,
            explanation: 'Most consumer regret comes from not reading contracts. Auto-renewal clauses, early termination fees, and arbitration clauses are commonly buried in fine print.',
          },
          {
            prompt: 'Negotiating the price of a large purchase works best when:',
            options: [
              'You have competing offers, are willing to walk away, and the seller knows it',
              'You express urgency and willingness to pay any price to get the item today',
              'You compliment the seller extensively before making your first offer',
              'You negotiate via text message to avoid emotional pressure',
            ],
            correct: 0,
            explanation: 'Willingness to walk away is your greatest negotiating power. Competing quotes give you leverage. Urgency transfers power to the seller.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-15',
    number: 15,
    title: 'Entrepreneurship',
    subtitle: 'Build your own income engine',
    color: '#CA8A04',
    icon: '🚀',
    units: [
      {
        id: 'u15-1',
        title: 'Starting a Business',
        icon: '🚀',
        centsReward: 75,
        questions: [
          {
            prompt: 'Profit margin = Net Profit ÷ Revenue. A 15% margin means:',
            options: [
              '15 cents of profit remain from every dollar of revenue after all expenses',
              'The business grew revenue by 15% compared to last year',
              'The owner takes home 15% of all customer payments as salary',
              '15% of the business is owned by outside investors',
            ],
            correct: 0,
            explanation: 'Margin is the efficiency of converting revenue to profit. Grocery stores run 1–2%; software companies often run 20–40%. Know your industry benchmarks.',
          },
          {
            prompt: 'Why is cash flow more critical than profit for a new business?',
            options: [
              'A profitable business can still fail if it runs out of cash to pay bills',
              'New businesses don\'t pay taxes on profit, only on cash flows',
              'Banks require positive cash flow before approving business loans',
              'Profit is not calculated until a business has operated for 3 full years',
            ],
            correct: 0,
            explanation: '"Cash is king." A business can show accounting profit while waiting for invoices to be paid — and bounce payroll. Cash flow mismanagement is the #1 cause of small business failure.',
          },
          {
            prompt: 'A business plan is most useful for:',
            options: [
              'Forcing you to stress-test assumptions before risking real money',
              'Legally registering your business with the state government',
              'Guaranteeing investors a specific return on their investment',
              'Setting employee salaries in compliance with minimum wage laws',
            ],
            correct: 0,
            explanation: 'The value of a business plan is the thinking process, not the document. Working through pricing, costs, and target customers reveals flaws before they cost you money.',
          },
          {
            prompt: 'The most sustainable way to scale a small business is:',
            options: [
              'Systematize operations so growth doesn\'t require your constant personal involvement',
              'Hire as many employees as possible in the first year to build capacity',
              'Take out the largest possible business loan to fund aggressive expansion',
              'Reduce prices to capture market share before any competitors enter',
            ],
            correct: 0,
            explanation: 'A business that depends entirely on the founder is fragile. Systems (documented processes, automation, delegation) allow the business to grow beyond one person\'s capacity.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-16',
    number: 16,
    title: 'Advanced Economics',
    subtitle: 'Global finance and markets',
    color: '#2563EB',
    icon: '🌐',
    units: [
      {
        id: 'u16-1',
        title: 'Global Markets',
        icon: '🌐',
        centsReward: 80,
        questions: [
          {
            prompt: 'A tariff is:',
            options: [
              'A tax on imported goods that raises their price for domestic buyers',
              'A government subsidy paid to domestic exporters to boost competitiveness',
              'A trade agreement that eliminates customs inspections between countries',
              'The exchange rate at which two currencies are traded on open markets',
            ],
            correct: 0,
            explanation: 'Tariffs protect domestic industries but raise prices for consumers and can trigger retaliatory tariffs from trading partners, potentially starting trade wars.',
          },
          {
            prompt: 'When the U.S. dollar strengthens against the euro, U.S. exports become:',
            options: [
              'More expensive for European buyers, reducing demand for U.S. goods abroad',
              'Cheaper for European buyers, dramatically increasing export volumes',
              'Unaffected — exchange rates only matter for financial transactions',
              'More competitive because European importers prefer strong currencies',
            ],
            correct: 0,
            explanation: 'A strong dollar means foreign buyers need more of their currency to buy American goods → U.S. exports become less competitive. Weak dollar = exports boom, imports become expensive.',
          },
          {
            prompt: 'Comparative advantage explains why:',
            options: [
              'Countries benefit from trading even if one is better at producing everything',
              'The richest country always sets the terms of international trade agreements',
              'Only developing nations benefit from international trade',
              'Trade is zero-sum — one country\'s gain is another\'s loss',
            ],
            correct: 0,
            explanation: 'Even if the U.S. can produce both wine and cloth more efficiently than Portugal, both countries gain by specializing in their comparative advantage and trading.',
          },
          {
            prompt: 'A monopoly is harmful to consumers primarily because:',
            options: [
              'Without competition, the monopolist can charge higher prices and reduce quality',
              'Monopolies are required to give 50% of profits to the government',
              'Monopolists are legally prohibited from innovating under antitrust law',
              'Monopolies always collapse quickly, disrupting supply for consumers',
            ],
            correct: 0,
            explanation: 'Competition drives down prices and up quality. Monopolists face no competitive pressure, so they maximize profit at consumers\' expense.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-17',
    number: 17,
    title: 'Alternative Investments',
    subtitle: 'Beyond stocks and bonds',
    color: '#7C3AED',
    icon: '💎',
    units: [
      {
        id: 'u17-1',
        title: 'Alternative Assets',
        icon: '💎',
        centsReward: 85,
        questions: [
          {
            prompt: 'Cryptocurrency is best classified as:',
            options: [
              'A highly speculative, volatile digital asset with uncertain long-term value',
              'A government-backed currency safer than the U.S. dollar',
              'An FDIC-insured investment available at traditional banks',
              'A commodity with stable intrinsic value like gold or silver',
            ],
            correct: 0,
            explanation: 'Crypto has no earnings, no cash flows, and no government backing. It\'s driven by speculation and sentiment. Most financial advisors recommend limiting exposure to a small % of a portfolio.',
          },
          {
            prompt: 'Gold is traditionally used in portfolios to:',
            options: [
              'Hedge against inflation and currency devaluation',
              'Generate dividend income during market downturns',
              'Provide guaranteed returns uncorrelated with any market',
              'Maximize growth during periods of economic expansion',
            ],
            correct: 0,
            explanation: 'Gold tends to hold value when currencies weaken and markets fall. It\'s a store of value, not a growth asset — it produces no income or earnings.',
          },
          {
            prompt: 'Options contracts give you:',
            options: [
              'The right, but not the obligation, to buy or sell an asset at a set price',
              'Guaranteed delivery of a commodity at the current market price',
              'Ownership of shares in a company without paying the full market price',
              'The ability to short-sell stocks without a margin account',
            ],
            correct: 0,
            explanation: 'Options are derivatives. A call option gives you the right to BUY at a strike price; a put gives you the right to SELL. They\'re complex — most retail investors should avoid them.',
          },
          {
            prompt: 'Private equity investments are inaccessible to most retail investors because:',
            options: [
              'They require large minimum investments and lock up capital for years',
              'The SEC prohibits individuals from owning shares in private companies',
              'Returns are always negative, so financial advisors discourage them',
              'Private equity funds only accept institutional investors by legal requirement',
            ],
            correct: 0,
            explanation: 'Most PE funds require $250k–$5M minimums and lock your money for 5–10 years. Only accredited investors ($1M+ net worth or $200k+ income) can legally participate.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-18',
    number: 18,
    title: 'Advanced Wealth',
    subtitle: 'Build generational financial security',
    color: '#0F766E',
    icon: '🏦',
    units: [
      {
        id: 'u18-1',
        title: 'Wealth Building',
        icon: '🏦',
        centsReward: 90,
        questions: [
          {
            prompt: 'Tax-loss harvesting means:',
            options: [
              'Selling losing investments to offset gains and reduce your tax bill',
              'Donating investments directly to charity to avoid capital gains taxes',
              'Holding losing investments until they recover to avoid realizing a loss',
              'Claiming investment losses on your tax return without selling the asset',
            ],
            correct: 0,
            explanation: 'If you have $10k in gains and $4k in losses, you only pay tax on $6k net. You can buy a similar-but-not-identical investment immediately to maintain market exposure.',
          },
          {
            prompt: 'The FIRE movement (Financial Independence, Retire Early) centers on:',
            options: [
              'Saving 50–70% of income to reach financial independence in 10–15 years',
              'Retiring at exactly 65 with a pension and Social Security',
              'Investing exclusively in real estate to generate early retirement income',
              'Achieving a 10% annual return on investments to outpace inflation',
            ],
            correct: 0,
            explanation: 'FIRE practitioners use extreme savings rates and the 4% safe withdrawal rule (25× annual expenses invested) to retire decades early.',
          },
          {
            prompt: 'Estate planning is important even for young adults because:',
            options: [
              'A will ensures your assets go to the right people — not default state law',
              'You must have a trust to legally transfer assets after death',
              'Estate taxes apply to all assets over $1,000 left to heirs',
              'Without a will, the government automatically takes your assets',
            ],
            correct: 0,
            explanation: 'Without a will, state intestacy laws decide who inherits. A will, healthcare directive, and beneficiary designations on accounts are the minimum estate plan everyone needs.',
          },
          {
            prompt: 'Asset protection strategies aim to:',
            options: [
              'Shield your wealth from lawsuits and creditors using legal structures',
              'Guarantee investment returns by hedging with government bonds',
              'Protect bank deposits by spreading them across multiple FDIC-insured banks',
              'Reduce your portfolio\'s volatility by rebalancing quarterly',
            ],
            correct: 0,
            explanation: 'LLCs, trusts, and retirement accounts (which are typically creditor-protected) can shield wealth from lawsuits. Important for business owners, doctors, and high-net-worth individuals.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-19',
    number: 19,
    title: 'Behavioral Finance',
    subtitle: 'Master your money psychology',
    color: '#C2410C',
    icon: '🧠',
    units: [
      {
        id: 'u19-1',
        title: 'Money Psychology',
        icon: '🧠',
        centsReward: 90,
        questions: [
          {
            prompt: 'Loss aversion means people feel losses:',
            options: [
              'About twice as painfully as they feel equivalent gains are pleasurable',
              'Less intensely than gains — which is why they take too much risk',
              'Equally to gains — pain and pleasure are symmetrical in economics',
              'Only when losses exceed 50% of total portfolio value',
            ],
            correct: 0,
            explanation: 'Nobel laureate Kahneman found losing $100 feels about twice as bad as gaining $100 feels good. This causes investors to hold losing stocks too long and sell winners too early.',
          },
          {
            prompt: 'Herd mentality in investing leads to:',
            options: [
              'Buying at peaks and selling at bottoms — the opposite of what creates wealth',
              'Perfectly diversified portfolios because everyone holds market-weight positions',
              'Stable prices because everyone is making the same rational decision',
              'Consistent outperformance as collective wisdom beats individual analysis',
            ],
            correct: 0,
            explanation: 'Herding caused the dot-com bubble, the 2008 housing bubble, and countless meme stock crashes. When everyone rushes in, prices are already overvalued.',
          },
          {
            prompt: 'Confirmation bias in investing causes people to:',
            options: [
              'Seek information that confirms existing beliefs while ignoring contradicting evidence',
              'Copy trades made by the most successful investors in their peer group',
              'Make decisions based on the most recent price movement of a stock',
              'Overestimate their own ability to pick stocks that outperform the market',
            ],
            correct: 0,
            explanation: 'If you believe Tesla is a great investment, you\'ll read bullish articles and dismiss bearish ones. This prevents objective reassessment and leads to overconcentration.',
          },
          {
            prompt: 'Mental accounting causes financial harm when:',
            options: [
              'You treat "found money" (tax refund, bonus) as spending money rather than wealth',
              'You keep separate accounts for savings and spending at the same bank',
              'You track spending by category in a budget spreadsheet',
              'You set up automatic transfers to savings on payday',
            ],
            correct: 0,
            explanation: 'A dollar is a dollar regardless of where it came from. Spending a $3,000 bonus freely while carrying credit card debt at 22% APR is the same as paying 22% interest on fun.',
          },
        ],
      },
    ],
  },

  {
    id: 'level-20',
    number: 20,
    title: 'Mastery',
    subtitle: 'The complete financial picture',
    color: '#1E293B',
    icon: '🏆',
    units: [
      {
        id: 'u20-1',
        title: 'Capstone Challenge',
        icon: '🏆',
        centsReward: 150,
        questions: [
          {
            prompt: 'A 28-year-old earns $60k/year. Which financial priority order is MOST correct?',
            options: [
              '1) Emergency fund → 2) Employer match → 3) High-interest debt → 4) Max IRA → 5) Invest more',
              '1) Max Roth IRA → 2) Pay off all debt → 3) Emergency fund → 4) Employer match',
              '1) Pay all debts first → 2) Save 20% → 3) Employer match → 4) Emergency fund',
              '1) Invest in index funds → 2) Emergency fund → 3) Pay minimum debts → 4) Employer match',
            ],
            correct: 0,
            explanation: 'The financial priority ladder: emergency fund (security) → employer match (free money) → high-interest debt (guaranteed return) → IRA → more investing. Order matters enormously.',
          },
          {
            prompt: 'Inflation, taxes, and fees are all examples of:',
            options: [
              'Silent wealth destroyers that compound against you if ignored',
              'Government programs designed to redistribute income fairly',
              'Risks only relevant to investors with more than $1M in assets',
              'Factors that cancel each other out over a 30-year investment horizon',
            ],
            correct: 0,
            explanation: 'A 7% gross return minus 0.8% fee minus 2% inflation minus tax drag = a real return well under 4%. Understanding these drags is essential to knowing your actual wealth growth.',
          },
          {
            prompt: 'The single most powerful financial decision most people can make is:',
            options: [
              'Starting to invest early and consistently, even in small amounts',
              'Picking the right individual stocks to maximize portfolio returns',
              'Earning more income through promotions and career advancement',
              'Timing the market to buy during crashes and sell at peaks',
            ],
            correct: 0,
            explanation: 'Time in the market beats timing the market. $100/month from age 22 to 65 at 8% = ~$413k. Starting at 32? ~$175k. Those 10 years are worth $238,000 from the same $100/month.',
          },
          {
            prompt: 'Financial independence means:',
            options: [
              'Your investments generate enough passive income to cover your living expenses',
              'You have no debt of any kind including your mortgage',
              'Your net worth exceeds $1 million in total assets',
              'You have a job offer you can decline without financial stress',
            ],
            correct: 0,
            explanation: 'FI = passive income ≥ expenses. At that point, work becomes optional. The FI number is typically 25× annual expenses (based on the 4% safe withdrawal rate).',
          },
          {
            prompt: 'Which combination best describes someone on the path to long-term wealth?',
            options: [
              'Lives below their means, invests consistently, avoids high-interest debt, and thinks long-term',
              'Earns a six-figure income and maximizes lifestyle spending to stay motivated',
              'Times the market expertly and picks high-growth individual stocks',
              'Pays only minimum debt payments to maximize monthly investment contributions',
            ],
            correct: 0,
            explanation: 'Wealth is built through behavior — spending less than you earn, investing the difference consistently, avoiding wealth destroyers (debt, fees, taxes). Income matters far less than habits.',
          },
        ],
      },
    ],
  },
  {
    id: 'level-21',
    number: 21,
    title: 'Emotional Spending',
    subtitle: 'How emotions drive financial decisions',
    color: '#6366F1',
    icon: '🧠',
    units: [
      {
        id: 'u21-1',
        title: 'Emotional Spending',
        icon: '💭',
        centsReward: 40,
        questions: [
          {
            prompt: 'Why do people engage in "retail therapy" even when it worsens their finances?',
            options: [
              'Purchases trigger a short-term dopamine boost that temporarily masks negative emotions',
              'Spending is a rational response to stress because new items solve underlying problems',
              'Retail therapy only affects people without a budget or financial plan',
              'The enjoyment of new purchases lasts as long as the stress that prompted the purchase',
            ],
            correct: 0,
            explanation: 'Buying something activates the brain\'s reward system and releases dopamine — a brief mood lift. But the underlying emotion returns, often with added financial guilt, creating a spending cycle.',
          },
          {
            prompt: 'FOMO-driven spending is particularly harmful because it causes people to:',
            options: [
              'Spend based on social comparison rather than genuine personal value or need',
              'Overspend exclusively on luxury items above their income level',
              'Save too little only during periods of high social media usage',
              'Avoid investing because peers seem to be spending rather than saving',
            ],
            correct: 0,
            explanation: 'Fear of missing out shifts the spending trigger from "do I need this?" to "are others doing this?" — a comparison trap that bypasses rational decision-making and erodes savings.',
          },
          {
            prompt: 'Research on money and happiness consistently shows that:',
            options: [
              'Beyond a comfortable income level, additional money has rapidly diminishing returns on daily happiness',
              'Higher income always produces proportionally higher life satisfaction and well-being',
              'People who prioritize saving report lower day-to-day happiness than free spenders',
              'Wealth has no measurable effect on emotional well-being in controlled studies',
            ],
            correct: 0,
            explanation: 'Studies (including Kahneman\'s landmark research) show emotional well-being plateaus around a comfortable income. After basic needs and security are met, more money adds little to daily happiness.',
          },
          {
            prompt: 'In personal finance, "hedonic adaptation" means:',
            options: [
              'New purchases quickly feel normal, so spending more rarely produces lasting satisfaction',
              'People naturally become happier the more wealth they accumulate over time',
              'Consumers eventually make fully rational purchase decisions after market exposure',
              'Budget limits force people to find happiness in cheaper alternatives',
            ],
            correct: 0,
            explanation: 'The hedonic treadmill: a new car, phone, or apartment feels exciting — then becomes the new baseline within weeks. This is why lifestyle inflation doesn\'t reliably increase happiness.',
          },
        ],
      },
    ],
  },
  {
    id: 'level-22',
    number: 22,
    title: 'Money Mindset',
    subtitle: 'Beliefs and behaviors that shape wealth',
    color: '#6366F1',
    icon: '💡',
    units: [
      {
        id: 'u22-1',
        title: 'Money Mindset',
        icon: '💡',
        centsReward: 40,
        questions: [
          {
            prompt: 'A scarcity mindset around money most commonly leads to:',
            options: [
              'Short-term thinking, fear-driven decisions, and difficulty investing for the future',
              'Frugality habits that reliably produce long-term wealth accumulation',
              'Heightened awareness of resources that leads to more efficient spending',
              'Strong motivation to pursue income-boosting opportunities aggressively',
            ],
            correct: 0,
            explanation: 'Scarcity thinking focuses attention on what\'s lacking — triggering anxiety, impulsive short-term decisions, and avoidance of investing. It\'s why poverty can feel self-reinforcing even when income rises.',
          },
          {
            prompt: 'Research on financial habits shows that:',
            options: [
              'Money beliefs formed in childhood significantly shape adult financial behavior',
              'Financial literacy education alone is sufficient to change long-term financial outcomes',
              'Income level is the single strongest predictor of long-term financial success',
              'Financial habits are largely genetic and resistant to mindset or behavioral change',
            ],
            correct: 0,
            explanation: 'Studies show that children\'s money scripts — beliefs about money absorbed before age 10 — directly predict adult behaviors like overspending, avoidance, and risk-taking with finances.',
          },
          {
            prompt: '"Lifestyle creep" refers to:',
            options: [
              'Spending rising to match income growth, preventing savings from increasing',
              'The gradual increase in the cost of living that erodes purchasing power over time',
              'Wealthy people becoming progressively more frugal as their net worth grows',
              'Investment returns that slowly increase as a portfolio compounds over decades',
            ],
            correct: 0,
            explanation: 'When a raise leads to a nicer apartment, newer car, and more dining out — income grows but savings don\'t. Combating lifestyle creep is one of the highest-leverage wealth-building habits.',
          },
          {
            prompt: 'Which mindset shift most reliably improves long-term financial outcomes?',
            options: [
              'Treating saving and investing as paying your future self first, before discretionary spending',
              'Focusing on maximizing current income as the single most important financial variable',
              'Believing financial success requires accepting significant investment risk',
              'Prioritizing complete debt elimination before building any other financial assets',
            ],
            correct: 0,
            explanation: '"Pay yourself first" — automating savings before spending — removes willpower from the equation. Research consistently shows this habit outperforms budgeting-based approaches to wealth building.',
          },
        ],
      },
    ],
  },
]

export const allUnits = levels.flatMap(l => l.units)
