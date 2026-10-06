output "domain_identifier_ids" {
  description = "IDs of the identifier copies Immuta created inside domains, keyed <domain>:<identifier>."
  value       = { for key, copy in immuta_domain_identifier.identifiers : key => copy.id }
}
