# Prestige vs. Performance: Global University Rankings Dashboard
**KU Leuven Data Visualisation [G0R05a] - 2026**

Decode global university rankings with our interactive data visualization dashboard! By comparing **Times Higher Education (THE)** and **QS** datasets alongside **World Bank** economic data, we expose "prestige bias" to help prospective students find high-value "Hidden Gems" based on true research and career impact, rather than just historical brand names.

🚀 **Live Interactive Dashboard Prototype:** [View the Interactive Dashboard Here](https://KULeuven-DataViz-Uni-Ranking-Group-2026.github.io/global-rankings-dashboard/dashboard/interactive-dashboard.html)

## 👥 Team Members
* YIN Renlong 
* Victor Kao 
* Lei Pei
* Szabó Gergely 
* Kawtar Darkaoui 
* Deborah Adelakun 

## 📂 Repository Structure
To keep our collaboration clean and organized, please place your files in the corresponding folders:

* 📁 **`/dashboard`** - Contains the interactive web application files (HTML, CSS, JS, or Streamlit/Dash).
* 📁 **`/data`** - Contains the raw and cleaned `.csv` datasets (THE, QS, World Bank).
* 📁 **`/presentations`** - Contains our intermediate PPT slides and the final mandatory PDF report.
* 📁 **`/scripts`** - Contains the Python scripts used for data cleaning, API integration, and exploratory static visualizations (Seaborn/Matplotlib).

## 📊 Data Sources
1. **Times Higher Education (THE) 2016-2026:** Longitudinal data measuring research output, industry impact, and teaching environment.
2. **QS World University Rankings 2026:** Cross-sectional data heavily emphasizing global Employer and Academic Reputation.
3. **World Bank Open Data API:** Live GDP per capita metrics to analyze the socio-economic drivers behind academic success.

---

## 📝 Development & Changelog
*A log to track major project milestones and backend updates.*



**[01 May 2026] - Subject Domain Analysis & Policy Pivot (YIN Renlong)**
* **Strategic Audience Pivot:** Following faculty feedback from the intermediate presentation, officially shifted the project's target audience from "Prospective Students" to "University Strategic Planners and Policymakers." This aligns the dashboard's macro-economic and institutional-level data with the correct user persona.
* **THE Subject Data Integration:** Imported, cleaned, and structured a new comprehensive dataset containing the 2026 THE Subject Rankings to explicitly answer faculty questions regarding how specific academic domains (Arts & Humanities vs. Engineering) dictate global standing.
* **Algorithmic Intra-Bin Interpolation:** Discovered and resolved a severe visual artifact ("grid clustering") caused by the publisher's binned ranking format (e.g., Rank 401-500). Engineered a custom *Lexicographical Tie-Breaking Algorithm* by extracting the exact decimal values of the five core metrics and applying the official THE formula weights (Teaching 30%, Research 30%, Citations 30%, International 7.5%, Industry 2.5%) to calculate a highly precise simulated proxy score. This successfully unmasked the true continuous distribution of the data without violating the publisher's primary hierarchy.
* **Advanced Visual Analytics:** Designed three new interactive scatter plots (Global Domain Strategy, Sub-Regional Micro-Geopolitics, and an EU-Specific Case Study) mapping Arts ranks against Engineering ranks. Adjusted coordinate axes (inverted to position Rank 1 at the top-right) and applied a 1:1 diagonal reference line to visually separate "Generalists" from "Specialists."
* **HCI Interaction Upgrades (Text Occlusion Fix):** Programmed custom `updatemenus` toggle buttons ("Show/Hide Names") directly into the Plotly layout. This allows users to hide labels to prevent text occlusion and cognitive overload during exploration, but instantly toggle labels back on for screenshot captures and details-on-demand. 
* **Computational Sociology Extraction:** Documented extensive geopolitical policy insights derived directly from the domain data, including the Anglosphere's "Halo Effect," the Asian/German "Tech Vanguard" scaling strategy, the "Capital Barrier" trapping the Global South, and the algorithmic penalization of hyper-specialized institutes (e.g., India's IITs).



**[01 May 2026] - UI/UX & Statistical Overhaul of Legacy Charts (YIN Renlong)**

* **Distribution Analysis Upgrade (Elite Volatility):** Replaced the cognitively overloading 14-line "spaghetti chart" of Elite Trajectories with a **Statistical Box Plot**. This mathematically visualizes the Interquartile Range (IQR), median stability, and specific historical outliers (e.g., Caltech's negative velocity), proving the "calcification" of the Top 5 universities.
* **Zero-Sum Market Share Conversion (Eastward Shift):** Upgraded the basic regional line chart into a **100% Stacked Area Chart** to correctly model the Global Top 200 as a finite, zero-sum geopolitical market. Augmented the visual with Python-calculated Linear Regression and CAGR statistics to prove the consistency ($R^2$ > 0.90) and exact velocity of the Asian market share expansion.
* **Histogram HCI Fix (Employability Paradox):** Transformed the monochromatic Z-Score histogram into a region-stacked distribution to visually prove the Anglosphere "Reputation Premium." Added an interactive **Marginal Rug Plot** along the X-axis to solve the standard histogram tooltip limitation, allowing users to hover over exact university data points within the binned tails.
* **Narrative Background Annotations (Methodology Clash):** Inverted the X and Y axes on the QS vs THE scatter plot to position Rank 1 at the top-right (aligning with psychological "best" perceptions). Hardcoded narrative text annotations directly onto the chart background ("Hidden Gems" and "The Old Guard") to transition the dashboard from raw data exploration to Guided Analytics.
* **Multi-Dimensional Scaling (Size Bias):** Applied the regional color-mapping algorithm to the Size Bias scatter plot, unmasking the geopolitical disconnect between Asian "Volume/Merge" strategies (favored by THE) and European "Boutique/Historical" strategies (favored by QS).
* **Accessibility & Standardization:** Enforced strict UI consistency across all legacy graphs (standardized 1200x900 resolution). Replaced default Plotly colors with the `Prism` high-contrast, colorblind-safe palette to meet course accessibility standards. Added dynamic X-axis padding to the GDP chart to prevent static label cut-offs (e.g., Luxembourg).



**[30 April 2026] - Data Engineering & UI/UX Architecture (Victor Kao)**

* **THE Subject Data Extraction:** Successfully reverse-engineered the *Times Higher Education* backend to bypass automated anti-bot protections, extracting a massive longitudinal dataset (70,000+ rows) of THE Subject Rankings from 2016 to 2026. Published this proprietary extraction publicly to Kaggle for team API access.
* **Data Formatting Pipeline:** Transformed complex, multi-tab spreadsheet outputs into clean, machine-readable `.csv` formats, optimizing the data structure for immediate Pandas/Python processing without IDE memory-overload issues.
* **Frontend Framework Evaluation:** Conducted rapid prototyping and evaluation of multiple advanced UI/UX frameworks (Flowbite, AdminLTE) and AI-assisted frontend builders (Lovable.dev, Claude Design) to establish the architectural roadmap for the dashboard's final frontend presentation.
* **LLM Workflow Optimization:** Implemented a highly efficient hybrid-AI development workflow. Delegated repetitive data-cleaning and formatting tasks to Gemini, strategically reserving Claude Pro's restricted context-window limits for complex frontend architectural generation.



**[27 April 2026] - Interactive Dashboard & Web Conversion (YIN Renlong)**

* Refactored all static Seaborn/Matplotlib charts into interactive **Plotly Express** web visualizations.
* Implemented "details-on-demand" interaction techniques (hover tooltips) allowing users to see specific university names, ranks, and countries across all datasets.
* Added programmatic static text labels to the GDP scatter plot to instantly highlight key geopolitical outliers (e.g., China, US) without relying on mouse interaction.
* Rewrote the project introduction to explicitly target prospective students and align with HCI/DataViz course terminology (Gestalt principles, graphical perception).
* Integrated a formal academic bibliography to mathematically justify our visual design choices.
* Muted all backend API and loading bar (`tqdm`) warnings via the Python `warnings` library to ensure a flawless frontend UI.
* Renamed the core Jupyter Notebook to `DataViz-intermediate-interactive-dashboard.ipynb` for clear team organization.
* Engineered a terminal-based conversion pipeline using `nbconvert` to transform the Python notebook into a pristine, code-hidden, interactive HTML webpage.



## 🛠️ How to Update the Interactive Dashboard (For Team Members)

If anyone on the team wants to edit the graphs, change the text, or update the analysis, you do not need to edit the HTML directly! Just follow this simple pipeline:

1. **Pull the latest code:** Make sure your local folder is up to date (`git pull origin main`).

2. **Edit the Notebook:** Open `DataViz-intermediate-interactive-dashboard.ipynb` in your local Jupyter environment or VS Code. Make your changes and save the file.

3. **Generate the Webpage:** Open your Terminal, navigate to the folder containing the notebook, and run this exact command:

   ```bash
   jupyter nbconvert --to html --execute --no-input --output interactive-dashboard.html DataViz-interactive-dashboard.ipynb
   ```

*(Note: --execute runs the code fresh, --no-input hides the python code, and --output automatically names the file).*

4. **Push to GitHub:** Add, commit, and push both the .ipynb and the new .html file. The website updates in 2 minutes!



**[22 April 2026] - Midterm Preparation & Architecture (YIN Renlong)**

* Set up the GitHub repository architecture and team collaboration folders.
* Integrated the World Bank API to map live GDP per capita to university rankings.
* Generated exploratory Data Analysis graphs (Seaborn) proving the "Prestige vs. Performance" gap and the "China Outlier" GDP trend.
* Wrote a `python-pptx` script to generate the Intermediate Presentation slides. 
* Configured repository visibility to Public and successfully deployed the live web prototype via GitHub Pages.
* Standardized dashboard file naming to web standards (`midterm-report.html`).

**[21 April 2026] - Initial Prototype (Victor Kao)**
* Pushed initial interactive HTML dashboard prototype for midterm feedback.

---

