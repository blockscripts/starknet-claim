# Starknet Airdrop Claim Script 🚀

This Python script facilitates claiming of tokens from the Starknet Airdrop. The script is designed to interact with the Starknet network, allowing users to claim and withdraw STRK tokens and withdraw ETH.

## Prerequisites 🛠️

- Python 3.9 or higher
- `pip` package manager

## Installation 📦

1. Clone the repository:

    ```bash
    git clone https://github.com/blockscripts/stark-claim.git
    ```

2. Navigate to the project directory:

    ```bash
    cd stark-claim/
    ```

3. Install the required packages:

    ```bash
    pip install -r requirements.txt
    ```

## Configuration ⚙️

1. Create a `.env` file in the project root based on the provided `.env.example`.
2. Fill out the `privkeys.txt` file with your private key and transfer address pairs, following the format in `privkeys.txt.example`.

## Usage 🚀

1. Run the script:

    ```bash
    python main.py
    ```

2. Choose the desired action:
   - **Claim and Withdraw STRK**: Claims STRK tokens and transfers them to specified addresses.
   - **Withdraw ETH**: Withdraws ETH from the deployed contract to specified addresses.
   - **Exit**: Exits the script.

3. Follow the instructions provided in the terminal.

## Additional Information ℹ️

### File Descriptions 📂

- `utils.py`: Contains utility functions used in the main script.
- `main.py`: The main script for claiming and withdrawing tokens.
- `config.py`: Configuration file using Pydantic for managing settings.
- `requirements.txt`: List of required Python packages.
- `privkeys.txt.example`: Example file for private key and transfer address pairs.
- `.env.example`: Example file for environment variables.

### Important Notes ⚠️

- Ensure that you have the correct settings in the `.env` file before running the script.
- Review and update the `privkeys.txt` file with your specific private key and transfer address pairs.
