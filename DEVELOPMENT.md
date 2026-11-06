# Clone repository # Enter project directory

git clone https://github.com/qatalyse/expense-splitter-Streamlit.git
cd expense-splitter-Streamlit

# Create virtual environment # Activate virtual environment

python3 -m venv .venv
source .venv/bin/activate

# Install requirements

pip install -r requirements.txt

# Run automated tests

python -m unittest discover -s tests

# Launch Application

streamlit run app.py

# deactivate environment

deactivate

# other

python3 --version
which python3
