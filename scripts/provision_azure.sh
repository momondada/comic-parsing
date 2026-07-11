#!/usr/bin/env bash
# One-time Azure provisioning for the comic-parsing webapp.
# Run this in Azure Cloud Shell (https://shell.azure.com) or any machine with
# the az CLI logged in (`az login`). Safe to re-run — every step is idempotent.
#
# Uses Managed Identity (not storage account keys) throughout: some tenants
# enforce "Key based authentication is not permitted on this storage account"
# via policy, so this avoids depending on key access being allowed at all.
set -euo pipefail

# ---- Edit these before running ----
RESOURCE_GROUP="comic-parsing-rg"
LOCATION="eastasia"
STORAGE_ACCOUNT="comicparsestorage"   # must be globally unique, lowercase, 3-24 chars, no hyphens
APP_SERVICE_PLAN="comic-parsing-plan"
WEBAPP_NAME="comic-parsing-app"          # must be globally unique
BLOB_CONTAINER="comic-pages"
AI_SERVICES_NAME="comic-parsing-ai"       # must be globally unique
# ------------------------------------

echo "==> Creating resource group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

echo "==> Creating storage account..."
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --output none

STORAGE_ACCOUNT_ID=$(az storage account show \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query id --output tsv)

echo "==> Creating blob container and tables (using your own az login, not account keys)..."
az storage container create \
  --name "$BLOB_CONTAINER" \
  --account-name "$STORAGE_ACCOUNT" \
  --auth-mode login \
  --output none

az storage table create --name jobs --account-name "$STORAGE_ACCOUNT" --auth-mode login --output none
az storage table create --name chapters --account-name "$STORAGE_ACCOUNT" --auth-mode login --output none

echo "==> Creating App Service plan (Linux, B1)..."
az appservice plan create \
  --name "$APP_SERVICE_PLAN" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --is-linux \
  --sku B1 \
  --output none

echo "==> Creating Web App (placeholder image, GitHub Actions will deploy the real one)..."
az webapp create \
  --name "$WEBAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --plan "$APP_SERVICE_PLAN" \
  --deployment-container-image-name "mcr.microsoft.com/appsvc/staticsite:latest" \
  --output none

echo "==> Enabling system-assigned Managed Identity on the Web App..."
PRINCIPAL_ID=$(az webapp identity assign \
  --name "$WEBAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query principalId --output tsv)

echo "==> Granting that identity access to the storage account..."
az role assignment create \
  --assignee-object-id "$PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Contributor" \
  --scope "$STORAGE_ACCOUNT_ID" \
  --output none

az role assignment create \
  --assignee-object-id "$PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Storage Table Data Contributor" \
  --scope "$STORAGE_ACCOUNT_ID" \
  --output none

echo "==> Creating Azure AI services resource..."
# NOTE: a plain "az cognitiveservices account create --kind AIServices" (as
# below) does NOT get Model deployments / Azure OpenAI support in every
# subscription — if "Model deployments" doesn't show up on this resource,
# create the OpenAI-capable resource via https://ai.azure.com (Azure AI
# Foundry) instead, deploy the model there (Global Standard deployment type
# avoids per-region GPU quota issues), then point AZURE_AI_SERVICES_ENDPOINT
# / AZURE_OPENAI_DEPLOYMENT at that resource instead of this one.
# If this tenant's policy also blocks public network access on this resource
# (as it did for Storage), the app will fail to reach it and the same fix
# applies: add a Private Endpoint (subresource "account") on comic-parsing-vnet
# + link the privatelink.cognitiveservices.azure.com DNS zone, same as Storage.
az cognitiveservices account create \
  --name "$AI_SERVICES_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --kind AIServices \
  --sku S0 \
  --yes \
  --output none

AI_SERVICES_ID=$(az cognitiveservices account show \
  --name "$AI_SERVICES_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query id --output tsv)

AI_SERVICES_ENDPOINT=$(az cognitiveservices account show \
  --name "$AI_SERVICES_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.endpoint --output tsv)

echo "==> Granting the Web App's identity access to the AI services resource..."
az role assignment create \
  --assignee-object-id "$PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Cognitive Services OpenAI User" \
  --scope "$AI_SERVICES_ID" \
  --output none

echo "==> Now deploy a vision-capable chat model (e.g. gpt-5.4-pro) onto"
echo "    this resource (or a Foundry-created one, see note above), then"
echo "    re-run/continue to set the app settings below with its deployment name."

echo "==> Configuring app settings and Always On..."
az webapp config appsettings set \
  --name "$WEBAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings \
    AZURE_STORAGE_ACCOUNT_NAME="$STORAGE_ACCOUNT" \
    BLOB_CONTAINER_NAME="$BLOB_CONTAINER" \
    AZURE_AI_SERVICES_ENDPOINT="$AI_SERVICES_ENDPOINT" \
    AZURE_OPENAI_DEPLOYMENT="gpt-5.4-pro" \
    WEBSITES_PORT=8000 \
    WEBSITES_ENABLE_APP_SERVICE_STORAGE=false \
  --output none

az webapp config set \
  --name "$WEBAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --always-on true \
  --output none

echo "==> Fetching publish profile (needed as a GitHub secret)..."
echo "    (requires SCM Basic Auth Publishing Credentials = On for this Web App)"
az webapp deployment list-publishing-profiles \
  --name "$WEBAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --xml > publish_profile.xml

cat <<EOF

Done. Next steps:

1. In the GitHub repo (momondada/comic-parsing) go to
   Settings -> Secrets and variables -> Actions, and add a secret named
   AZURE_WEBAPP_PUBLISH_PROFILE with the contents of ./publish_profile.xml
   (then delete that local file — it grants deploy access to the app).

2. In the same repo, go to Settings -> Secrets and variables -> Actions ->
   Variables tab, and add a repository VARIABLE (not secret) named
   AZURE_WEBAPP_NAME with the value:
   $WEBAPP_NAME

3. Push to main (touching anything under webapp/) to trigger the deploy
   workflow, which builds the image, pushes it to GHCR, and points this
   Web App at it. The first run will push a new GHCR package
   (ghcr.io/<owner>/comic-parsing-webapp) as private by default — go to that
   package's settings on GitHub and change its visibility to Public, so the
   Web App can pull it without registry credentials.

4. Once deployed, visit the Web App's Default domain shown on its Overview
   page in the Azure Portal (newer subscriptions get a random-suffixed
   hostname, not just https://$WEBAPP_NAME.azurewebsites.net).
EOF
