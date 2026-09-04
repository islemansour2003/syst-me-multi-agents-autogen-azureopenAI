#requires -Version 5.1
<#
Déploiement du système multi-agents sur Azure Container Apps, avec
Application Insights (+ alertes) et auto-scaling — ticket "Déploiement
production".

À NE PAS exécuter d'un coup : ce script crée de vraies ressources Azure
facturées. Lance-le bloc par bloc (sélectionne les lignes dans VS Code /
PowerShell ISE et exécute avec F8), vérifie chaque résultat avant de
continuer.

Prérequis : `az login` déjà fait, extension containerapp installée
(le script l'installe si absente).
#>

# ============================================================
# 0. Variables — adapte ces valeurs avant de lancer quoi que ce soit
# ============================================================
$RESOURCE_GROUP      = "rg-multiagents-poc"
$LOCATION            = "francecentral"          # ou "westeurope"
$ACR_NAME            = "acrmultiagentspoc"       # doit être unique globalement, alphanum uniquement
$LOG_ANALYTICS_NAME  = "log-multiagents-poc"
$APP_INSIGHTS_NAME   = "appi-multiagents-poc"
$CONTAINERAPPS_ENV   = "cae-multiagents-poc"
$CONTAINER_APP_NAME  = "ca-multiagents-poc"
$IMAGE_NAME           = "multiagents-app"
$IMAGE_TAG            = "v1"
$ALERT_EMAIL          = "TON_EMAIL_ICI@example.com"   # <-- remplace par ton adresse pour recevoir les alertes

# ============================================================
# 1. Connexion + extension containerapp
# ============================================================
az login
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.Insights

# ============================================================
# 2. Groupe de ressources
# ============================================================
az group create --name $RESOURCE_GROUP --location $LOCATION

# ============================================================
# 3. Azure Container Registry (ACR) + build & push de l'image
#    (az acr build construit ET pousse l'image côté Azure, pas besoin
#    de Docker en local ni de docker push manuel)
# ============================================================
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic --admin-enabled true

az acr build --registry $ACR_NAME --image "$IMAGE_NAME`:$IMAGE_TAG" .

# ============================================================
# 4. Log Analytics workspace + Application Insights (lié au même workspace)
#    -> c'est ce qui capture automatiquement les logs JSON stdout du conteneur
# ============================================================
az monitor log-analytics workspace create `
    --resource-group $RESOURCE_GROUP `
    --workspace-name $LOG_ANALYTICS_NAME

$LOG_ANALYTICS_ID = az monitor log-analytics workspace show `
    --resource-group $RESOURCE_GROUP --workspace-name $LOG_ANALYTICS_NAME `
    --query customerId -o tsv

$LOG_ANALYTICS_KEY = az monitor log-analytics workspace get-shared-keys `
    --resource-group $RESOURCE_GROUP --workspace-name $LOG_ANALYTICS_NAME `
    --query primarySharedKey -o tsv

az monitor app-insights component create `
    --app $APP_INSIGHTS_NAME `
    --resource-group $RESOURCE_GROUP `
    --location $LOCATION `
    --workspace $LOG_ANALYTICS_NAME `
    --kind web `
    --application-type web

$APPINSIGHTS_CONNECTION_STRING = az monitor app-insights component show `
    --app $APP_INSIGHTS_NAME --resource-group $RESOURCE_GROUP `
    --query connectionString -o tsv

# ============================================================
# 5. Environnement Container Apps, relié au Log Analytics workspace
# ============================================================
az containerapp env create `
    --name $CONTAINERAPPS_ENV `
    --resource-group $RESOURCE_GROUP `
    --location $LOCATION `
    --logs-workspace-id $LOG_ANALYTICS_ID `
    --logs-workspace-key $LOG_ANALYTICS_KEY

# ============================================================
# 6. Déploiement de l'application (secrets = variables sensibles du .env)
#    Remplace les valeurs par tes vraies clés (ne les mets JAMAIS en clair
#    dans un fichier versionné — exécute ces lignes directement dans ton
#    terminal, pas depuis un script commité).
# ============================================================
$ACR_SERVER = az acr show --name $ACR_NAME --query loginServer -o tsv
$ACR_USER   = az acr credential show --name $ACR_NAME --query username -o tsv
$ACR_PASS   = az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv

az containerapp create `
    --name $CONTAINER_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --environment $CONTAINERAPPS_ENV `
    --image "$ACR_SERVER/$IMAGE_NAME`:$IMAGE_TAG" `
    --registry-server $ACR_SERVER `
    --registry-username $ACR_USER `
    --registry-password $ACR_PASS `
    --target-port 8501 `
    --ingress external `
    --min-replicas 0 `
    --max-replicas 5 `
    --secrets `
        azure-openai-key="TA_CLE_AZURE_OPENAI" `
        news-api-key="TA_CLE_NEWSAPI" `
    --env-vars `
        AZURE_OPENAI_API_KEY=secretref:azure-openai-key `
        NEWS_API_KEY=secretref:news-api-key `
        AZURE_OPENAI_ENDPOINT="TON_ENDPOINT" `
        AZURE_OPENAI_API_VERSION="TA_VERSION" `
        AZURE_OPENAI_DEPLOYMENT_ID="TON_DEPLOYMENT_ID" `
        AZURE_OPENAI_MODEL="TON_MODELE" `
        APPLICATIONINSIGHTS_CONNECTION_STRING=$APPINSIGHTS_CONNECTION_STRING

# ============================================================
# 7. Auto-scaling : règle basée sur la concurrence HTTP
#    (0 replica au repos -> jusqu'à 5, scale-up dès 20 requêtes concurrentes
#    par replica)
# ============================================================
az containerapp update `
    --name $CONTAINER_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --scale-rule-name http-scale-rule `
    --scale-rule-type http `
    --scale-rule-http-concurrency 20 `
    --min-replicas 0 `
    --max-replicas 5

# ============================================================
# 8. Alertes Application Insights (groupe d'action + règle)
#    Ex: alerte si des exceptions sont levées dans les 5 dernières minutes
# ============================================================
az monitor action-group create `
    --resource-group $RESOURCE_GROUP `
    --name "ag-multiagents-alerts" `
    --short-name "magents" `
    --email-receiver name="admin" email=$ALERT_EMAIL

$APPINSIGHTS_ID = az monitor app-insights component show `
    --app $APP_INSIGHTS_NAME --resource-group $RESOURCE_GROUP --query id -o tsv

az monitor scheduled-query create `
    --resource-group $RESOURCE_GROUP `
    --name "alerte-exceptions-multiagents" `
    --scopes $APPINSIGHTS_ID `
    --condition "count 'exceptions | where timestamp > ago(5m)' > 0" `
    --condition-query "exceptions | where timestamp > ago(5m)" `
    --description "Alerte si une exception est levée par le système multi-agents" `
    --evaluation-frequency 5m `
    --window-size 5m `
    --severity 2 `
    --action-groups "ag-multiagents-alerts"

# ============================================================
# 9. Récupérer l'URL publique de l'application
# ============================================================
az containerapp show `
    --name $CONTAINER_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --query properties.configuration.ingress.fqdn -o tsv

# ============================================================
# NETTOYAGE (à la fin, pour éviter toute facturation résiduelle) :
#   az group delete --name $RESOURCE_GROUP --yes --no-wait
# ============================================================
