export const units = [
  {
    id: 'unit-1',
    number: 1,
    title: 'Money Basics',
    description: 'Build your financial foundation',
    color: 'var(--accent)',
    lessons: [
      {
        id: 'budgeting-basics',
        title: 'Budgeting Basics',
        icon: '💰',
        centsReward: 50,
        questions: [
          {
            prompt: 'What is the main purpose of a budget?',
            options: [
              'To plan how to spend and save your money',
              'To track your credit card rewards points',
              'To calculate how much tax you owe',
              'To apply for a bank loan',
            ],
            correct: 0,
            explanation: 'A budget is a spending plan that helps you allocate income toward expenses, savings, and goals.',
          },
          {
            prompt: 'In the 50/30/20 rule, what does the 20% represent?',
            options: [
              'Savings and debt repayment',
              'Wants like dining out and travel',
              'Essential needs like rent and food',
              'Federal and state income taxes',
            ],
            correct: 0,
            explanation: '50% goes to needs, 30% to wants, and 20% to savings and paying down debt.',
          },
          {
            prompt: 'Which of these is a "need" in a budget?',
            options: [
              'Monthly rent payment',
              'Streaming service subscription',
              'Weekend restaurant meals',
              'New clothing for fun',
            ],
            correct: 0,
            explanation: 'Needs are essential expenses you cannot live without, like housing, utilities, and groceries.',
          },
          {
            prompt: 'What should you do FIRST when building a budget?',
            options: [
              'Calculate your total monthly take-home income',
              'List all the things you want to purchase',
              'Open a high-yield savings account',
              'Cancel all your subscriptions immediately',
            ],
            correct: 0,
            explanation: 'You need to know how much money is coming in before you can plan where it all goes.',
          },
        ],
      },
      {
        id: 'saving-emergency-funds',
        title: 'Emergency Funds',
        icon: '🏦',
        centsReward: 50,
        questions: [
          {
            prompt: 'How many months of expenses should an emergency fund cover?',
            options: ['3–6 months', '6–10 months', '1–2 months', '10–12 months'],
            correct: 0,
            explanation: 'Financial experts recommend 3–6 months of living expenses to cover job loss or unexpected costs.',
          },
          {
            prompt: 'Where is the best place to keep an emergency fund?',
            options: [
              'A high-yield savings account',
              'Invested in individual stocks',
              'A long-term CD locked for 5 years',
              'A retirement account like a 401(k)',
            ],
            correct: 0,
            explanation: 'A high-yield savings account keeps money accessible while earning more interest than a standard account.',
          },
          {
            prompt: 'What does "paying yourself first" mean?',
            options: [
              'Moving money to savings before spending on anything else',
              'Buying what you want before paying monthly bills',
              'Negotiating a higher salary at work',
              'Paying off all debt before opening a savings account',
            ],
            correct: 0,
            explanation: 'Automating savings the moment your paycheck arrives ensures you save consistently before other spending.',
          },
          {
            prompt: 'Which habit most reliably helps you save more each month?',
            options: [
              'Tracking every purchase you make',
              'Using only credit cards for purchases',
              'Skipping a formal budget entirely',
              'Keeping all money in one checking account',
            ],
            correct: 0,
            explanation: 'Tracking spending reveals where money leaks happen so you can redirect that cash to savings.',
          },
        ],
      },
    ],
    test: {
      id: 'unit-1-test',
      title: 'Unit 1 Test',
      icon: '🏆',
      isTest: true,
      centsReward: 120,
      questions: [
        {
          prompt: 'You earn $3,000/month. Using the 50/30/20 rule, how much goes to savings?',
          options: ['$600', '$900', '$1,500', '$300'],
          correct: 0,
          explanation: '20% of $3,000 = $600 toward savings and debt repayment each month.',
        },
        {
          prompt: 'Your car breaks down unexpectedly. Which resource should cover this first?',
          options: [
            'Your emergency fund',
            'A payday loan',
            'Your retirement account',
            'A credit card cash advance',
          ],
          correct: 0,
          explanation: 'Emergency funds exist exactly for this — unexpected, necessary expenses that aren\'t in your regular budget.',
        },
        {
          prompt: 'Which combo best describes a healthy financial foundation?',
          options: [
            'A written budget + 3 months of savings set aside',
            'High credit card limits + a retirement account',
            'No debt + no savings account',
            'High income + no formal spending plan',
          ],
          correct: 0,
          explanation: 'Knowing where your money goes (budget) and having a safety net (emergency fund) are the two pillars of financial health.',
        },
        {
          prompt: 'You get a $500 bonus. What does "paying yourself first" say to do with it?',
          options: [
            'Transfer it to savings before spending any of it',
            'Treat yourself since you earned it',
            'Use it to pay next month\'s bills early',
            'Invest all of it in the stock market immediately',
          ],
          correct: 0,
          explanation: 'Paying yourself first means savings is the first "bill" you pay — before any discretionary spending.',
        },
        {
          prompt: 'A friend says budgets are too restrictive. What\'s the best counter?',
          options: [
            'Budgets give you permission to spend — guilt-free — within your plan',
            'Budgets are only useful if you are in debt',
            'Budgets should only track needs, not wants',
            'Budgets work best when you skip tracking small purchases',
          ],
          correct: 0,
          explanation: 'A budget is a freedom tool, not a restriction — it tells you exactly how much you can spend on fun without guilt.',
        },
      ],
    },
  },
  {
    id: 'unit-2',
    number: 2,
    title: 'Credit & Borrowing',
    description: 'Master credit scores and smart borrowing',
    color: 'var(--quaternary)',
    lessons: [
      {
        id: 'understanding-credit',
        title: 'Credit Scores',
        icon: '💳',
        centsReward: 60,
        questions: [
          {
            prompt: 'What FICO score range is considered "good"?',
            options: ['670–739', '580–620', '740–799', '300–499'],
            correct: 0,
            explanation: 'FICO scores run from 300–850. Scores from 670–739 are "good," while 740+ is "very good" or "exceptional."',
          },
          {
            prompt: 'Which factor has the BIGGEST impact on your FICO credit score?',
            options: [
              'Payment history',
              'Types of credit accounts',
              'Length of credit history',
              'Number of hard inquiries',
            ],
            correct: 0,
            explanation: 'Payment history makes up 35% of your FICO score — the single largest factor by far.',
          },
          {
            prompt: 'What is credit utilization?',
            options: [
              'The percentage of your credit limit currently in use',
              'The number of credit cards you currently own',
              'How often you apply for new credit products',
              'The total dollar amount of debt you carry',
            ],
            correct: 0,
            explanation: 'Keeping utilization below 30% (ideally below 10%) signals responsible credit management to lenders.',
          },
          {
            prompt: 'How long does a missed payment typically stay on your credit report?',
            options: ['7 years', '2 years', '10 years', '18 months'],
            correct: 0,
            explanation: 'Most negative marks, including late payments, remain on your credit report for 7 years.',
          },
        ],
      },
      {
        id: 'avoiding-debt-traps',
        title: 'Avoiding Debt Traps',
        icon: '⚠️',
        centsReward: 60,
        questions: [
          {
            prompt: 'What makes payday loans so financially dangerous?',
            options: [
              'They carry extremely high APRs, often 300–400%',
              'They require a strong credit score to qualify',
              'They take several months to receive after approval',
              'They are only available in certain states',
            ],
            correct: 0,
            explanation: 'Payday loan fees trap borrowers in debt cycles because the cost of borrowing is far higher than most people realize.',
          },
          {
            prompt: 'Using the avalanche method, which debt do you pay off first?',
            options: [
              'The one with the highest interest rate',
              'The one with the smallest remaining balance',
              'The most recent debt you took on',
              'The one with the largest minimum payment',
            ],
            correct: 0,
            explanation: 'The avalanche method targets the most expensive debt first, saving the most money in total interest paid.',
          },
          {
            prompt: 'Why is only paying the credit card minimum dangerous?',
            options: [
              'Interest piles up on the balance, stretching repayment for years',
              'It immediately triggers a drop in your credit score',
              'The bank can close your account after 3 months',
              'Minimum payments are reported as missed to credit bureaus',
            ],
            correct: 0,
            explanation: 'A $3,000 balance at 20% APR on minimum payments alone can take 14+ years and cost thousands in interest.',
          },
          {
            prompt: 'What debt-to-income (DTI) ratio do most lenders prefer?',
            options: ['Below 36%', 'Between 40–50%', 'Above 50%', 'Exactly 25%'],
            correct: 0,
            explanation: 'A DTI below 36% shows lenders you have enough breathing room in your budget to handle new debt responsibly.',
          },
        ],
      },
    ],
    test: {
      id: 'unit-2-test',
      title: 'Unit 2 Test',
      icon: '🏆',
      isTest: true,
      centsReward: 140,
      questions: [
        {
          prompt: 'Your credit utilization is 65%. What\'s the best immediate action?',
          options: [
            'Pay down balances to get under 30%',
            'Apply for more credit cards to raise your limit',
            'Close your oldest credit card account',
            'Dispute the utilization with the credit bureau',
          ],
          correct: 0,
          explanation: 'Paying down balances directly reduces utilization. Never close old accounts — that hurts your score by reducing available credit and shortening history.',
        },
        {
          prompt: 'You have three debts: 5% auto loan, 22% credit card, 8% student loan. Avalanche order?',
          options: [
            '22% credit card → 8% student loan → 5% auto loan',
            '5% auto loan → 8% student loan → 22% credit card',
            '8% student loan → 22% credit card → 5% auto loan',
            'All three equally at the same time',
          ],
          correct: 0,
          explanation: 'Avalanche = highest interest first. Attack the 22% card, then student loan, then auto loan.',
        },
        {
          prompt: 'A payday lender charges $15 per $100 borrowed for 2 weeks. What\'s the approximate APR?',
          options: ['~390%', '~15%', '~30%', '~78%'],
          correct: 0,
          explanation: '$15/$100 × 26 periods/year ≈ 390% APR. This is why payday loans are so costly.',
        },
        {
          prompt: 'Which action would MOST directly improve a poor credit score?',
          options: [
            'Making every payment on time for 12 consecutive months',
            'Opening several new credit accounts at once',
            'Settling old debts for less than the full amount',
            'Checking your credit score weekly',
          ],
          correct: 0,
          explanation: 'Payment history is 35% of your FICO score — consistent on-time payments are the single most powerful credit builder.',
        },
        {
          prompt: 'What is the key difference between the snowball and avalanche repayment methods?',
          options: [
            'Snowball targets smallest balances; avalanche targets highest interest rates',
            'Snowball costs less interest overall; avalanche builds motivation faster',
            'Snowball is for credit cards only; avalanche works for all debt types',
            'Snowball requires minimum payments only; avalanche requires extra payments',
          ],
          correct: 0,
          explanation: 'Avalanche saves more money. Snowball builds momentum. Both work — the best one is the one you\'ll stick to.',
        },
      ],
    },
  },
  {
    id: 'unit-3',
    number: 3,
    title: 'Growing Wealth',
    description: 'Put compound growth to work for you',
    color: 'var(--secondary)',
    lessons: [
      {
        id: 'interest-and-growth',
        title: 'Compound Interest',
        icon: '📈',
        centsReward: 70,
        questions: [
          {
            prompt: 'What makes compound interest different from simple interest?',
            options: [
              'You earn interest on previously earned interest too',
              'The rate changes every month based on the market',
              'It only applies to loans, not savings accounts',
              'It requires a minimum balance of $10,000',
            ],
            correct: 0,
            explanation: 'Compound interest is "interest on interest" — it accelerates growth over time.',
          },
          {
            prompt: 'The Rule of 72 helps you estimate how long it takes to ___.',
            options: [
              'Double your money at a given interest rate',
              'Pay off a credit card balance completely',
              'Determine how much tax you owe on gains',
              'Qualify for a mortgage at a given income',
            ],
            correct: 0,
            explanation: 'Divide 72 by your annual rate to estimate years to double (e.g., 72 ÷ 6% = 12 years).',
          },
          {
            prompt: 'As a BORROWER, which type of interest costs you more over time?',
            options: [
              'Compound interest',
              'Simple interest',
              'Fixed interest',
              'Variable interest',
            ],
            correct: 0,
            explanation: 'With compound interest on a loan, interest accrues on the unpaid interest too — making your total cost higher.',
          },
          {
            prompt: 'APY on a savings account stands for ___.',
            options: [
              'Annual Percentage Yield',
              'Average Payment Yearly',
              'Adjusted Principal Yield',
              'Automatic Payment Year',
            ],
            correct: 0,
            explanation: 'APY reflects the real return after compounding over a full year — always compare APY when shopping savings accounts.',
          },
        ],
      },
      {
        id: 'investing-fundamentals',
        title: 'Investing 101',
        icon: '🚀',
        centsReward: 70,
        questions: [
          {
            prompt: 'What do you actually own when you buy a stock?',
            options: [
              'A share of ownership in that company',
              'A loan you made to that company',
              'A guaranteed fixed return each year',
              'A government-insured savings certificate',
            ],
            correct: 0,
            explanation: 'Stocks represent equity — you own a piece of the company and share in its profits and losses.',
          },
          {
            prompt: 'What is the main goal of diversification?',
            options: [
              'Spread risk so one bad investment does not sink you',
              'Maximize returns by focusing on one hot sector',
              'Reduce the number of accounts you manage',
              'Qualify for lower brokerage trading fees',
            ],
            correct: 0,
            explanation: '"Don\'t put all eggs in one basket" — diversification limits the damage when any single investment underperforms.',
          },
          {
            prompt: 'An index fund is best described as ___.',
            options: [
              'A fund that passively tracks a market index like the S&P 500',
              'A fund actively managed to beat the market each quarter',
              'A government savings bond with a fixed interest rate',
              'A type of checking account with investment features',
            ],
            correct: 0,
            explanation: 'Index funds offer broad diversification at low cost. Warren Buffett recommends them for most everyday investors.',
          },
          {
            prompt: 'Why does starting to invest at 22 vs. 32 matter so much?',
            options: [
              'Compound growth has 10 extra years to multiply your money',
              'Stock prices are always lower when you are younger',
              'Brokerage firms charge less in fees for young investors',
              'The government matches contributions for people under 25',
            ],
            correct: 0,
            explanation: 'Those extra 10 years of compounding can mean hundreds of thousands more at retirement — time is your biggest asset.',
          },
        ],
      },
    ],
    test: {
      id: 'unit-3-test',
      title: 'Unit 3 Test',
      icon: '🏆',
      isTest: true,
      centsReward: 160,
      questions: [
        {
          prompt: 'You invest $5,000 at 6% annually. Using the Rule of 72, when does it double?',
          options: ['~12 years', '~6 years', '~18 years', '~24 years'],
          correct: 0,
          explanation: '72 ÷ 6 = 12 years. At 12 years your $5,000 becomes ~$10,000 without adding a single extra dollar.',
        },
        {
          prompt: 'You\'re 22 and can invest $200/month at 8% average return. Why does starting NOW beat starting at 32?',
          options: [
            'Each year of compound growth builds on all previous growth, snowballing over decades',
            'Market returns are always higher for younger investors',
            'Brokerage fees are waived for investors under 25',
            'Tax rates are lower on investments made before age 30',
          ],
          correct: 0,
          explanation: 'Compounding turns time into money. Starting 10 years earlier can more than double your ending balance.',
        },
        {
          prompt: 'A savings account offers 5% APY vs. a CD at 5.2% APR. Which actually pays more?',
          options: [
            'The savings account — APY already includes compounding',
            'The CD — a higher number always means more earnings',
            'They are identical — APY and APR are the same metric',
            'It depends entirely on your tax bracket',
          ],
          correct: 0,
          explanation: 'APY bakes in compounding. You need to calculate APY from APR to compare fairly — a 5.2% APR compounded monthly ≈ 5.33% APY.',
        },
        {
          prompt: 'Which portfolio is most diversified?',
          options: [
            '60% US index fund, 20% international index fund, 20% bond fund',
            '100% in one top-performing tech stock',
            '50% in real estate, 50% in gold',
            '10 different individual stocks in the same industry',
          ],
          correct: 0,
          explanation: 'True diversification spans asset classes (stocks, bonds) and geographies (US, international) — not just multiple picks within one sector.',
        },
        {
          prompt: 'Compound interest works FOR you in savings accounts and AGAINST you in ___.',
          options: [
            'High-interest loans and credit card debt',
            'Index fund investments',
            'Government savings bonds',
            'Employer 401(k) matches',
          ],
          correct: 0,
          explanation: 'The same mathematical force that grows your savings exponentially also grows unpaid debt exponentially. Pay off high-interest debt as fast as you can.',
        },
      ],
    },
  },
]

export const allItems = units.flatMap(u => [
  ...u.lessons,
  { ...u.test, isTest: true },
])
