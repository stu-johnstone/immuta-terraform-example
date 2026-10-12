# Every YAML file in policies/ is one global policy, in the Immuta V2 policy
# format. Adding a file adds a policy and deleting a file deletes it.
# Requires the GOVERNANCE permission.
resource "immuta_global_policy" "policies" {
  for_each = fileset("${path.module}/policies", "*.yaml")

  policy = file("${path.module}/policies/${each.value}")

  # The policies refer to tags, groups and attributes by name, so create those
  # first.
  depends_on = [
    immuta_tag.tags,
    immuta_group.groups,
  ]
}
