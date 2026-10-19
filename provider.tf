# Terraform workspaces represent environments (see README). Each environment's
# settings, including the Immuta host, come from environments/<environment>.tfvars,
# which the Makefile passes with -var-file. Only non-prod is implemented; add a
# tfvars file and a matching workspace to add another.
variable "immuta_host" {
  description = "URL of the Immuta tenant, for example https://example.hosted.immutacloud.com/."
  type        = string
}

# The API key is read from the IMMUTA_API_KEY environment variable.
provider "immuta" {
  host = var.immuta_host
}
