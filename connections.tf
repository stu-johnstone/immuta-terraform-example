# Each connection's secret comes from a sensitive variable, set through a
# TF_VAR_ environment variable, and is never written to the repository:
#
#   export TF_VAR_databricks_token="..."
#   export TF_VAR_redshift_password="..."
#
# To add another platform, such as Trino, add a variable (for example
# trino_password), an entry in local.connection_secrets and an entry in
# local.connections.
# Non-secret settings you do not want to commit, such as hosts and usernames,
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

variable "snowflake_host" {
  description = "Snowflake account host name, for example abc12345.us-east-1.snowflakecomputing.com."
  type        = string
}

variable "snowflake_warehouse" {
  description = "Snowflake warehouse Immuta runs its queries on."
  type        = string
}

variable "snowflake_role" {
  description = "Snowflake role Immuta connects with, created by the connection setup script."
  type        = string
}

variable "snowflake_username" {
  description = "Snowflake user Immuta connects with; its public key must be set in Snowflake."
  type        = string
}

variable "snowflake_private_key_file" {
  description = "Path to the Snowflake user's unencrypted PKCS#8 RSA private key (.p8). See README.md."
  type        = string
  default     = "~/.ssh/immuta_snowflake_key.p8"

  validation {
    condition     = fileexists(pathexpand(var.snowflake_private_key_file))
    error_message = "No private key at snowflake_private_key_file. Create it as described in README.md (Snowflake key pair)."
  }

  validation {
    condition     = !endswith(var.snowflake_private_key_file, ".pub")
    error_message = "snowflake_private_key_file must be the private key (.p8), not the public key (.pub)."
  }
}

locals {
  snowflake_private_key = sensitive(file(pathexpand(var.snowflake_private_key_file)))
}

variable "redshift_host" {
  description = "Redshift cluster or workgroup endpoint host name, without the port or database."
  type        = string
}

variable "redshift_username" {
  description = "Redshift user Immuta connects with."
  type        = string
}

variable "redshift_password" {
  description = "Password of the Redshift user Immuta connects with."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.redshift_password) > 0
    error_message = "Set TF_VAR_redshift_password to the Redshift user's password."
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
    snowflake  = { privateKey = { filename = "immuta_snowflake_key.p8", content = local.snowflake_private_key } }
    redshift   = { password = var.redshift_password }
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
