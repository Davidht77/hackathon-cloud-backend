# hackathon-cloud-backend

## CI/CD with GitHub Actions

This project is configured for automated deployment using GitHub Actions. The workflow is defined in <mcfile name="deploy.yml" path=".github/workflows/deploy.yml"></mcfile> and will automatically deploy the serverless API on every push to the `main` branch.

### Workflow Details

- **File**: <mcfile name="deploy.yml" path=".github/workflows/deploy.yml"></mcfile>
- **Trigger**: Push to the `main` branch.
- **Steps**:
  1.  **Checkout code**.
  2.  **Set up Python 3.9**.
  3.  **Install dependencies**: Installs Python dependencies from `requirements.txt` and Serverless Framework CLI with `serverless-python-requirements` plugin.
  4.  **Deploy to AWS**: Deploys the service to AWS using `serverless deploy`.

### Configuration

Ensure you have configured the following GitHub Secrets in your repository for the deployment to succeed:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`