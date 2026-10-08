# Example data. Add or change entries here; the resources in the other .tf
# files create one Immuta object per entry.
#
# Map keys (for example `jane` or `engineering`) are stable Terraform
# identifiers. Renaming a key replaces the Immuta object, so treat keys as IDs.

locals {
  domains = {
    research = {
      name                  = "Research"
      description           = "Domain for the research organisation"
      reference_identifiers = []
    }

    engineering = {
      name                  = "Engineering"
      description           = "Domain for the engineering organisation"
      reference_identifiers = []
    }

    finance = {
      name        = "Finance"
      description = "Domain for the finance organisation"

      # Keys from local.identifiers. Immuta copies each reference identifier
      # into the domain; the original is left untouched.
      reference_identifiers = ["credit_card"]
    }
  }

  # Key => fully qualified tag name. Tags are hierarchical, and Immuta creates
  # missing parents (here "Discovered").
  tags = {
    credit_card            = "Discovered.Credit card"
    primary_color          = "Discovered.Primary color"
    employee_name          = "Discovered.Employee Name"
    internal_employee_data = "HR Framework.Internal Employee Data"
  }

  # Classification frameworks apply a tag to columns based on tags already
  # found on the column, its neighbouring columns or its data source.
  frameworks = {
    hr = {
      short_name  = "HR Information v2"
      name        = "HR Information Framework v2"
      description = "Finds internal employee information and tags it for HR."
      active      = true

      # Tags used by the framework (keys from local.tags) => confidentiality
      # sensitivity: 0 non-sensitive, 1 sensitive, 2 highly sensitive, or null
      # for none.
      tags = {
        internal_employee_data = 1
      }

      # Each rule applies `classification_tag` when one of its criteria tags
      # is found. Criteria are `column_tags` (same column),
      # `neighbor_column_tags` (any column in the data source) and
      # `table_tags` (the data source); omit the ones a rule does not use.
      rules = {
        employee_data = {
          name                 = "Employee data"
          classification_tag   = "internal_employee_data"
          neighbor_column_tags = ["employee_name"]
        }
      }
    }
  }

  # Identifiers apply tags (keys from local.tags) to matching columns.
  # `domain = null` makes a tenant-wide reference identifier; set it to a key
  # from local.domains to create the identifier inside that domain.
  identifiers = {
    # regex: matches column values.
    credit_card = {
      name        = "Credit card"
      description = "Columns that hold a card number"
      type        = "regex"
      regex       = "[0-9]{16}"
      tags        = ["credit_card"]
      domain      = null
    }

    # columnNameRegex: matches column names instead of their values.
    credit_card_column = {
      name        = "Credit card columns"
      description = "Columns whose name suggests they hold a card number"
      type        = "columnNameRegex"
      regex       = "(card|pan)_?(number|no)"
      tags        = ["credit_card"]
      domain      = null
    }

    # dictionary: matches column values against a fixed list.
    primary_color_dictionary = {
      name           = "Primary color names"
      description    = "Columns that hold one of the primary colors by name"
      type           = "dictionary"
      values         = ["red", "green", "blue"]
      case_sensitive = false
      tags           = ["primary_color"]
      domain         = null
    }

    # Created directly inside the Finance domain.
    finance_primary_color = {
      name        = "Primary colors"
      description = "Columns that hold a primary color"
      type        = "regex"
      regex       = "(red|green|blue)"
      tags        = ["primary_color"]
      domain      = "finance"
    }
  }

  # Connections to data platforms. `configuration` is the connections API
  # registration payload, using its key names, without the credential.
  # `credential` holds only the non-secret credential fields; the secret is
  # added from a sensitive variable in connections.tf.
  #
  # Replace the placeholder values with your own. Changing a connection's key
  # or technology, or a setting the API cannot update (for Databricks: host,
  # port, immutaSystemCatalog, excludeGroupPattern), replaces the connection.
  connections = {
    databricks = {
      technology = "Databricks"

      credential = {
        authenticationType = "Token"
      }

      configuration = {
        clientConfiguration = {
          # From environments/<environment>.tfvars, which is not committed.
          host                = var.databricks_host
          path                = var.databricks_path
          port                = 443
          immutaSystemCatalog = "immuta_stu_j"
        }
        policyConfiguration = {
          excludeGroupPattern = "admins"
        }
        auditConfiguration = {
          enabled      = false
          workspaceIds = ["0000000000000000"]
        }
        dataObjectSync = {
          enabled   = true
          startTime = 0
          schedule  = "EVERY_24_HOURS"
        }
        syncOnCreate = true
        # owners is added in connections.tf from data.immuta_user.data_owner,
        # so no profile ID is hard-coded.
        dataObjectDefaults = {
          syncPolicy = false
        }
      }
    }
  }

  users = {
    jane = {
      user_id     = "jane.doe@example.com"
      name        = "Jane Doe"
      email       = "jane.doe@example.com"
      permissions = ["CREATE_PROJECT"]

      # Attribute name => list of values.
      attributes = {
        Department = ["Finance"]
        Region     = ["APAC", "EMEA"]
      }
    }

    ada = {
      user_id     = "ada.lovelace@example.com"
      name        = "Ada Lovelace"
      email       = "ada.lovelace@example.com"
      permissions = []
      attributes  = {}
    }

    alan = {
      user_id     = "alan.turing@example.com"
      name        = "Alan Turing"
      email       = "alan.turing@example.com"
      permissions = []
      attributes  = {}
    }
  }

  groups = {
    engineering = {
      name        = "Engineering"
      description = "Engineering department"
      email       = "engineering@example.com"

      # Keys from local.users.
      members = ["jane", "alan"]

      # Attribute name => value.
      attributes = {
        Department = "Engineering"
      }
    }

    research = {
      name        = "Research"
      description = "Research department"
      email       = "research@example.com"
      members     = ["ada", "jane"]

      attributes = {
        Department = "Research"
      }
    }
  }
}
