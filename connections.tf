# Each connection's secret comes from a sensitive variable, set through a
# TF_VAR_ environment variable, and is never written to the repository:
#
#   export TF_VAR_databricks_token="..."
#
# To add Snowflake or Trino, add a variable (for example snowflake_client_secret
# or trino_password), an entry in local.connection_secrets and an entry in
# local.connections.
# Non-secret settings you do not want to commit, such as the Databricks host,
# come from environments/<environment>.tfvars, which is gitignored and passed
# in by the Makefile (see environments/non-prod.tfvars.example).
variable "databricks_host" {
  description = "Databricks workspace host name, for example dbc-1234abcd-5678.cloud.databricks.com."
  type        = string
}

variable "databricks_path" {
  description = "HTTP path of the Databricks SQL warehouse, for example /sql/1.0/warehouses/1234abcd5678efgh."
  type        = string
}

variable "data_owner_email" {
  description = "Email of the existing Immuta user who owns the data objects connections register."
  type        = string
}

variable "databricks_token" {
  description = "Databricks personal access token Immuta connects with."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.databricks_token) > 0
    error_message = "Set TF_VAR_databricks_token to a Databricks personal access token."
  }
}

# The owner of the data objects each connection registers, looked up by email
# so that no profile ID is hard-coded. Needs the USER_ADMIN permission.
data "immuta_user" "data_owner" {
  email = var.data_owner_email
}

locals {
  # id is the profile ID as a string; Immuta returns a number, so a string
  # would show as a change on every plan.
  connection_owners = [{ type = "USER", id = tonumber(data.immuta_user.data_owner.id) }]

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
  configuration = jsonencode(merge(each.value.configuration, {
    dataObjectDefaults = merge(each.value.configuration.dataObjectDefaults, {
      owners = local.connection_owners
    })
  }))
  credential = jsonencode(merge(each.value.credential, local.connection_secrets[each.key]))

  # Destroying or replacing a connection deletes every data object registered
  # through it in Immuta. Remove this to deliberately destroy a connection.
  lifecycle {
    prevent_destroy = true
  }
}
