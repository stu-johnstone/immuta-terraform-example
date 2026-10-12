resource "immuta_domain" "domains" {
  for_each = local.domains

  name        = each.value.name
  description = each.value.description
}

locals {
  # One entry per reference identifier copied into a domain, keyed
  # "<domain>:<identifier>" (e.g. "finance:credit_card").
  domain_identifiers = {
    for copy in flatten([
      for domain_key, domain in local.domains : [
        for identifier_key in domain.reference_identifiers : {
          domain     = domain_key
          identifier = identifier_key
        }
      ]
    ]) : "${copy.domain}:${copy.identifier}" => copy
  }
}

# Immuta copies the reference identifier into the domain. The copy has its own
# ID; destroying this resource deletes only the copy.
resource "immuta_domain_identifier" "identifiers" {
  for_each = local.domain_identifiers

  domain_id            = immuta_domain.domains[each.value.domain].id
  source_identifier_id = immuta_identifier.identifiers[each.value.identifier].id
}

# Every data source with one of the domain's tags is in the domain. The
# business unit tags are applied to the Harbourstone schemas in
# data_objects.tf.
resource "immuta_domain_dynamic_assignment" "assignments" {
  for_each = { for key, domain in local.domains : key => domain if length(domain.assignment_tags) > 0 }

  domain_id = immuta_domain.domains[each.key].id
  tags      = [for tag in each.value.assignment_tags : immuta_tag.tags[tag].name]
}
