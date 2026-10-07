locals {
  # Immuta tag references are a name plus the catalog the tag comes from;
  # "curated" is any tag managed in Immuta.
  tag_refs = {
    for key, tag in immuta_tag.tags : key => { name = tag.name, source = "curated" }
  }
}

# Every update sends the whole framework, so changes made in the Immuta UI are
# overwritten on the next apply. Requires the GOVERNANCE permission.
resource "immuta_framework" "frameworks" {
  for_each = local.frameworks

  short_name  = each.value.short_name
  name        = each.value.name
  description = each.value.description
  active      = each.value.active

  # Referencing immuta_tag (through local.tag_refs) creates the tags first.
  tags = [
    for tag, sensitivity in each.value.tags : merge(local.tag_refs[tag], {
      sensitivities = sensitivity == null ? null : [
        { dimension = "confidentiality", sensitivity = sensitivity },
      ]
    })
  ]

  # Immuta rejects an empty criteria set, so unused criteria are left unset.
  rules = [
    for rule in values(each.value.rules) : {
      name                 = rule.name
      classification_tag   = local.tag_refs[rule.classification_tag]
      column_tags          = can(rule.column_tags) ? [for tag in rule.column_tags : local.tag_refs[tag]] : null
      neighbor_column_tags = can(rule.neighbor_column_tags) ? [for tag in rule.neighbor_column_tags : local.tag_refs[tag]] : null
      table_tags           = can(rule.table_tags) ? [for tag in rule.table_tags : local.tag_refs[tag]] : null
    }
  ]
}
