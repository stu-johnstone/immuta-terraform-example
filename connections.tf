# Each connection's secret comes from a sensitive variable, set through a
# TF_VAR_ environment variable, and is never written to the repository:
#
#   export TF_VAR_databricks_token="..."
#
# To add Snowflake or Trino, add a variable (for example snowflake_client_secret
# or trino_password), an entry in local.connection_secrets and an entry in
# local.connections.
variable "databricks_token" {
  description = "Databricks personal access token Immuta connects with."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.databricks_token) > 0
    error_message = "Set TF_VAR_databricks_token to a Databricks personal access token."
  }
}

locals {
  # Secret credential fields by connection key, merged into the non-secret
  # fields from local.connections.
  connection_secrets = {
    databricks = { token = var.databricks_token }
  }
}

# Requires the APPLICATION_ADMIN permission.
resource "immuta_connection" "connections" {
  for_each = local.connections

  connection_key = each.key
  technology     = each.value.technology
  configuration  = jsonencode(each.value.configuration)
  credential     = jsonencode(merge(each.value.credential, local.connection_secrets[each.key]))

  # Destroying or replacing a connection deletes every data object registered
  # through it in Immuta. Remove this to deliberately destroy a connection.
  lifecycle {
    prevent_destroy = true
  }
}
