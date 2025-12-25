# Kubernetes Quick Start Guide

Fast track deployment for Google Calendar to Discord sync on Kubernetes.

## Prerequisites

- Kubernetes cluster (1.21+)
- `kubectl` configured
- Docker image built and pushed
- Google OAuth2 credentials (`credentials.json`)
- Discord bot token and channel ID

## Option 1: Automated Deployment (Recommended)

Use the automated deployment script:

```bash
cd examples/kubernetes/scripts

# Deploy with custom image and schedule
./deploy.sh \
  --image your-registry/gcal-to-discord:latest \
  --schedule "*/30 * * * *" \
  --namespace gcal-to-discord
```

The script will:
1. ✅ Validate prerequisites
2. ✅ Build and push Docker image (optional)
3. ✅ Create namespace
4. ✅ Create secrets (interactive)
5. ✅ Deploy ConfigMap
6. ✅ Deploy CronJob

## Option 2: Manual Deployment

### Step 1: Create Namespace

```bash
kubectl create namespace gcal-to-discord
```

### Step 2: Create Secrets

```bash
# Use the helper script
cd examples/kubernetes/scripts
./create-secrets.sh

# Or manually:
kubectl create secret generic gcal2discord-discord-bot-token \
  --from-literal=token=YOUR_DISCORD_BOT_TOKEN \
  -n gcal-to-discord

kubectl create secret generic gcal2discord-google-credentials \
  --from-file=credentials.json=/path/to/credentials.json \
  -n gcal-to-discord
```

### Step 3: Configure and Deploy

```bash
cd examples/kubernetes

# Edit ConfigMap with your Discord channel ID
nano configmap.yaml

# Apply manifests
kubectl apply -f configmap.yaml
kubectl apply -f cronjob.yaml
```

All credentials are stored as Kubernetes Secrets.

## Verify Deployment

```bash
# Check CronJob
kubectl get cronjob -n gcal-to-discord

# View logs
kubectl logs -l app=gcal-to-discord -n gcal-to-discord -f

# Trigger manual run
kubectl create job --from=cronjob/gcal-to-discord-sync test-run -n gcal-to-discord
```

## Common Commands

### Monitoring

```bash
# Watch CronJob status
kubectl get cronjob -n gcal-to-discord -w

# List all jobs
kubectl get jobs -n gcal-to-discord

# View recent events
kubectl get events -n gcal-to-discord --sort-by='.lastTimestamp'

# Check resource usage
kubectl top pods -n gcal-to-discord
```

### Debugging

```bash
# Describe CronJob
kubectl describe cronjob gcal-to-discord-sync -n gcal-to-discord

# View pod logs (latest)
kubectl logs -l app=gcal-to-discord -n gcal-to-discord --tail=100

# View logs from specific job
kubectl logs job/gcal-to-discord-sync-28345678 -n gcal-to-discord

# Check secrets
kubectl get secrets -n gcal-to-discord
kubectl describe secret gcal2discord-discord-bot-token -n gcal-to-discord
```

### Updating

```bash
# Update ConfigMap
kubectl edit configmap gcal-to-discord-config -n gcal-to-discord

# Update secret
kubectl delete secret gcal2discord-discord-bot-token -n gcal-to-discord
kubectl create secret generic gcal2discord-discord-bot-token \
  --from-literal=token=NEW_TOKEN \
  -n gcal-to-discord

# Update schedule
kubectl edit cronjob gcal-to-discord-sync -n gcal-to-discord

# Force restart (delete running pods)
kubectl delete pods -l app=gcal-to-discord -n gcal-to-discord
```

## Cleanup

```bash
# Use cleanup script
cd examples/kubernetes/scripts
./cleanup.sh --namespace gcal-to-discord

# Or manually delete namespace (removes everything)
kubectl delete namespace gcal-to-discord
```

## Troubleshooting

### CronJob Not Running

```bash
# Check events
kubectl describe cronjob gcal-to-discord-sync -n gcal-to-discord

# Check if suspended
kubectl get cronjob gcal-to-discord-sync -n gcal-to-discord -o jsonpath='{.spec.suspend}'

# Resume if suspended
kubectl patch cronjob gcal-to-discord-sync -n gcal-to-discord -p '{"spec":{"suspend":false}}'
```

### Authentication Errors

```bash
# Verify secrets exist
kubectl get secrets -n gcal-to-discord

# Check secret contents
kubectl get secret gcal2discord-google-credentials -n gcal-to-discord -o yaml

# Re-create secret
kubectl delete secret gcal2discord-google-credentials -n gcal-to-discord
kubectl create secret generic gcal2discord-google-credentials \
  --from-file=credentials.json=./credentials.json \
  -n gcal-to-discord
```

### Image Pull Errors

```bash
# Check image name in CronJob
kubectl get cronjob gcal-to-discord-sync -n gcal-to-discord -o jsonpath='{.spec.jobTemplate.spec.template.spec.containers[0].image}'

# Add image pull secret if using private registry
kubectl create secret docker-registry registry-creds \
  --docker-server=your-registry \
  --docker-username=your-username \
  --docker-password=your-password \
  -n gcal-to-discord

# Update CronJob to use image pull secret
kubectl patch cronjob gcal-to-discord-sync -n gcal-to-discord -p '
{
  "spec": {
    "jobTemplate": {
      "spec": {
        "template": {
          "spec": {
            "imagePullSecrets": [{"name": "registry-creds"}]
          }
        }
      }
    }
  }
}'
```

## Schedule Examples

Edit `cronjob.yaml` before deploying:

```yaml
# Every 15 minutes
schedule: "*/15 * * * *"

# Every hour
schedule: "0 * * * *"

# Every 2 hours
schedule: "0 */2 * * *"

# At 9 AM and 5 PM
schedule: "0 9,17 * * *"

# Every 30 minutes during business hours (9 AM - 5 PM, weekdays)
schedule: "*/30 9-17 * * 1-5"

# Once per day at midnight
schedule: "0 0 * * *"
```

## Resource Requirements

Typical resource usage:

```yaml
resources:
  requests:
    memory: "64Mi"   # Minimum
    cpu: "50m"
  limits:
    memory: "256Mi"  # Maximum
    cpu: "500m"
```

Adjust based on your needs:
- Small calendars (<20 events): Use minimums
- Large calendars (100+ events): Increase limits
- Monitor with: `kubectl top pods -n gcal-to-discord`

## Security Best Practices

1. **Use dedicated service account**:
   ```bash
   kubectl create serviceaccount gcal-to-discord -n gcal-to-discord
   # Add to cronjob.yaml: serviceAccountName: gcal-to-discord
   ```

2. **Enable Pod Security Standards**:
   ```bash
   kubectl label namespace gcal-to-discord \
     pod-security.kubernetes.io/enforce=restricted
   ```

3. **Use external secret manager** (e.g., AWS Secrets Manager, Vault)

4. **Rotate secrets regularly**:
   ```bash
   # Update Discord token
   kubectl create secret generic gcal2discord-discord-bot-token \
     --from-literal=token=NEW_TOKEN \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

## Performance Tips

1. **Use longer sync intervals** if real-time updates aren't critical
2. **Set appropriate resource limits** to prevent resource contention
3. **Use node selectors** for dedicated nodes if needed:
   ```yaml
   nodeSelector:
     workload-type: batch
   ```

4. **Enable cluster autoscaling** to scale nodes based on demand

## Support

For detailed documentation, see:
- [Full Kubernetes Guide](README.md)
- [Main Project README](../../README.md)
- [Scheduling Guide](../../SCHEDULING.md)

For issues:
- Check logs: `kubectl logs -l app=gcal-to-discord -n gcal-to-discord`
- View events: `kubectl get events -n gcal-to-discord`
- Review CronJob: `kubectl describe cronjob gcal-to-discord-sync -n gcal-to-discord`
