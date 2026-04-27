# Prestige vs. Performance: Global University Rankings Dashboard
**KU Leuven Data Visualisation [G0R05a] - 2026**

Decode global university rankings with our interactive data visualization dashboard! By comparing **Times Higher Education (THE)** and **QS** datasets alongside **World Bank** economic data, we expose "prestige bias" to help prospective students find high-value "Hidden Gems" based on true research and career impact, rather than just historical brand names.

🚀 **Live Interactive Dashboard Prototype:** [View the Interactive Dashboard Here](https://KULeuven-DataViz-Uni-Ranking-Group-2026.github.io/intermediate-group-presentations/dashboard/interactive-dashboard.html)

🚀 **Live Dashboard Prototype:** [View the Midterm Report Here](https://KULeuven-DataViz-Uni-Ranking-Group-2026.github.io/intermediate-group-presentations/dashboard/midterm-report.html)

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
   jupyter nbconvert --to html --execute --no-input --output interactive-dashboard.html DataViz-intermediate-interactive-dashboard.ipynb
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

