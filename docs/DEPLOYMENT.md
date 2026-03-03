# Puerto Rico Molty - Deployment Instructions

## Quick Start

### 1. Register the Agent

First, register your agent with Moltbook:

```bash
python src/agent.py --register
```

Save the `api_key` and `claim_url` from the response. Send the claim URL to yourself, verify your email, and post a tweet to claim your agent.

### 2. Build the Container

```bash
cd puerto-rico-molty
docker build -t puerto-rico-molty .
```

### 3. Push to MicroK8s Registry

```bash
docker tag puerto-rico-molty localhost:32000/puerto-rico-molty:latest
docker push localhost:32000/puerto-rico-molty:latest
```

### 4. Deploy to MicroK8s

```bash
# Update the API key in the secret
export MOLTBOOK_API_KEY="moltbook_xxx"

# Apply with env override (or edit deployment.yaml)
kubectl apply -k k8s/
```

## Configuration

Edit `config.yaml` to customize:

- Agent name and description
- Heartbeat interval
- Auto-post settings
- Target submolts

## Files

```
puerto-rico-molty/
├── config.yaml          # Agent configuration
├── Dockerfile           # Container image
├── requirements.txt     # Python dependencies
├── src/
│   └── agent.py        # Main agent code
└── k8s/
    ├── deployment.yaml # K8s deployment + secret
    └── kustomization.yaml
```
