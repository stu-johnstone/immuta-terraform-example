# Settings and tags on the Harbourstone data objects that the Databricks
# connection registers. Load data/harbourstone_financial/databricks first (see
# data/README.md); the data objects are looked up by path, and a lookup waits
# up to 10 minutes for a data object the connection has not registered yet.
variable "harbourstone_catalog" {
  description = "Databricks catalog the Harbourstone Financial data was loaded into."
  type        = string
  default     = "harbourstone"
}

locals {
  # Schemas, keyed by business unit (e.g. "insurance"), and gold tables, keyed
  # "<schema>.<table>" (e.g. "insurance.gold_loss_ratio"), with the tag (a key
  # from local.tags) each one gets.
  harbourstone_data_object_tags = merge(
    {
      for schema, unit in local.business_units : schema => {
        path = [var.harbourstone_catalog, schema]
        tag  = unit.tag
      }
    },
    {
      for table in flatten([
        for schema, unit in local.business_units : [
          for name in unit.gold_tables : { schema = schema, name = name }
        ]
        ]) : "${table.schema}.${table.name}" => {
        path = [var.harbourstone_catalog, table.schema, table.name]
        tag  = "gold"
      }
    },
  )
}

# The connection registers data objects with data policies turned off
# (dataObjectDefaults.syncPolicy in locals.tf). Turn them on for the
# Harbourstone catalog; its schemas and tables inherit the setting.
resource "immuta_data_object_settings" "harbourstone" {
  connection_key = immuta_connection.connections["databricks"].connection_key
  path           = [var.harbourstone_catalog]
  sync_policy    = true
}

data "immuta_data_object" "harbourstone" {
  for_each = local.harbourstone_data_object_tags

  connection_key = immuta_connection.connections["databricks"].connection_key
  path           = each.value.path
}

# Business unit tags on schemas are inherited by their tables, so subscription
# policies and domains can match on them.
resource "immuta_data_object_tag" "harbourstone" {
  for_each = local.harbourstone_data_object_tags

  connection_key = data.immuta_data_object.harbourstone[each.key].connection_key
  data_object_id = data.immuta_data_object.harbourstone[each.key].id
  tag_id         = immuta_tag.tags[each.value.tag].id
}
