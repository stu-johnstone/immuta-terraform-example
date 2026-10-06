# Terraform workspaces represent environments (see README). Only non-prod is
# implemented; add another entry here and a matching workspace to add one.
locals {
  environments = {
    non-prod = {
      host = "https://i8xs1yfnyn2g81okkoa1zivf8e.hosted.immutacloud.com/"
    }
  }

  environment = local.environments[terraform.workspace]
}

# The API key is read from the IMMUTA_API_KEY environment variable.
provider "immuta" {
  host = local.environment.host
}
