# Data products from local.data_products. The Request app API needs its own
# URL and token: set request_app_url in environments/<environment>.tfvars and
# IMMUTA_REQUEST_APP_TOKEN in the environment (see README.md). Without
# request_app_url no data products are managed, so environments without the
# Request app can still plan and apply everything else.
locals {
  managed_data_products = var.request_app_url == null ? {} : local.data_products
}

# Subject matter experts, by email. The Request app identifies them by global
# user ID, which is looked up from their username and identity manager.
data "immuta_user" "data_product_experts" {
  for_each = toset([for product in local.managed_data_products : product.subject_matter_expert])

  email = each.value
}

data "immuta_global_user" "data_product_experts" {
  for_each = data.immuta_user.data_product_experts

  username = each.value.user_id
  iam_id   = each.value.iam_id
}

# Request forms, by name. Immuta requires them to create a data product.
data "immuta_request_form" "data_products" {
  for_each = toset([for product in local.managed_data_products : product.request_form])

  name = each.value
}

# The data sources in each data product's domain.
data "immuta_domain_data_sources" "data_products" {
  for_each = local.managed_data_products

  domain_id = immuta_domain.domains[each.value.domain].id
}

resource "immuta_data_product" "data_products" {
  for_each = local.managed_data_products

  name                     = each.value.name
  description              = each.value.description
  domains                  = [immuta_domain.domains[each.value.domain].id]
  subject_matter_expert_id = data.immuta_global_user.data_product_experts[each.value.subject_matter_expert].global_user_id

  data_access_request_form_id       = data.immuta_request_form.data_products[each.value.request_form].id
  masking_exception_request_form_id = data.immuta_request_form.data_products[each.value.request_form].id

  # Data source names end in the table name, for example
  # "databricks"."stu_catalog"."insurance"."gold_loss_ratio".
  data_sources = [
    for data_source in data.immuta_domain_data_sources.data_products[each.key].data_sources :
    data_source.id if contains(each.value.tables, trim(reverse(split(".", data_source.name))[0], "\""))
  ]
}
