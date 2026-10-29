resource "immuta_tag" "tags" {
  for_each = local.tags

  name = each.value
}

resource "immuta_identifier" "identifiers" {
  for_each = local.identifiers

  name        = each.value.name
  description = each.value.description
  type        = each.value.type
  domain_id   = each.value.domain == null ? null : immuta_domain.domains[each.value.domain].id

  # Referencing immuta_tag (rather than typing the tag name) makes Terraform
  # create the tags first; Immuta rejects identifiers that use unknown tags.
  tags = [for tag in each.value.tags : immuta_tag.tags[tag].name]

  # Type-specific settings: `regex` for regex and columnNameRegex, `values` and
  # `case_sensitive` for dictionary. Unused settings are left unset.
  #
  # Column name regexes are written in lower case (Databricks) and matched in
  # upper case too (Snowflake), e.g. "^region$|^REGION$". They must not use
  # escapes such as \d, which upper() would change.
  regex = (
    each.value.type == "columnNameRegex"
    ? "${each.value.regex}|${upper(each.value.regex)}"
    : try(each.value.regex, null)
  )
  values         = try(each.value.values, null)
  case_sensitive = try(each.value.case_sensitive, null)
}
