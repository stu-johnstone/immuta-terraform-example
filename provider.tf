# Terraform workspaces represent environments (see README). Each environment's
# settings, including the Immuta host, come from environments/<environment>.tfvars,
# which the Makefile passes with -var-file. Only non-prod is implemented; add a
# tfvars file and a matching workspace to add another.
variable "immuta_host" {
  description = "URL of the Immuta tenant, for example https://example.hosted.immutacloud.com/."
  type        = string
}

variable "request_app_url" {
  description = "Regional URL of the Request app (formerly Marketplace) API, for example https://na.api.immutacloud.com/marketplace. Needed for data products."
  type        = string
  default     = null
}

# The API key is read from the IMMUTA_API_KEY environment variable, and the
# Request app token from IMMUTA_REQUEST_APP_TOKEN.
provider "immuta" {
  host            = var.immuta_host
  request_app_url = var.request_app_url
}
