resource "immuta_domain" "domains" {
  for_each = local.domains

  name        = each.value.name
  description = each.value.description
}
