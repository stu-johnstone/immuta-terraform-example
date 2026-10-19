# Example data for the demo in DEMO.md, using the Harbourstone Financial Group
# data in data/harbourstone_financial. Add or change entries here; the
# resources in the other .tf files create one Immuta object per entry.
#
# Map keys (for example `cassandra` or `analytics`) are stable Terraform
# identifiers. Renaming a key replaces the Immuta object, so treat keys as IDs.

locals {
  # Harbourstone's businesses: one Databricks schema each (in
  # var.harbourstone_catalog). Each schema is tagged with `tag` (a key from
  # local.tags), which business unit subscription policies and domains match
  # on, and each gold table is tagged "Data Layer.Gold" for executive insights.
  business_units = {
    retail_banking = {
      tag         = "bu_retail_banking"
      gold_tables = ["gold_daily_deposits", "gold_customer_360", "gold_complaint_themes", "gold_aml_overview", "gold_home_loan_portfolio"]
    }

    commercial_banking = {
      tag         = "bu_commercial_banking"
      gold_tables = ["gold_risk_profile", "gold_portfolio_by_industry", "gold_arrears_monthly"]
    }

    insurance = {
      tag         = "bu_insurance"
      gold_tables = ["gold_loss_ratio", "gold_claims_overview", "gold_catastrophe_exposure"]
    }
  }

  # One domain per business unit. `assignment_tags` (keys from local.tags)
  # assign every data source with one of the tags to the domain.
  domains = {
    retail_banking = {
      name            = "Retail Banking"
      description     = "Harbourstone retail banking: customers, accounts, cards, home loans, complaints and AML"
      assignment_tags = ["bu_retail_banking"]

      # Keys from local.identifiers. Immuta copies each reference identifier
      # into the domain; the original is left untouched.
      reference_identifiers = ["financial_account"]
    }

    commercial_banking = {
      name                  = "Commercial Banking"
      description           = "Harbourstone commercial lending: business customers, facilities, covenants and credit reviews"
      assignment_tags       = ["bu_commercial_banking"]
      reference_identifiers = []
    }

    insurance = {
      name                  = "Insurance"
      description           = "Harbourstone general insurance: policyholders, policies, claims and fraud flags"
      assignment_tags       = ["bu_insurance"]
      reference_identifiers = []
    }
  }

  # Key => fully qualified tag name. Tags are hierarchical, and Immuta creates
  # missing parents (for example "PII"). The policies in policies/ refer to
  # these names.
  tags = {
    # Applied to columns by identifiers.
    pii_name              = "PII.Name"
    pii_date_of_birth     = "PII.Date of Birth"
    pii_contact_details   = "PII.Contact Details"
    pii_government_id     = "PII.Government ID"
    pii_financial_account = "PII.Financial Account"
    region                = "Data.Region"

    # Applied to schemas and tables in data_objects.tf.
    bu_retail_banking     = "Business Unit.Retail Banking"
    bu_commercial_banking = "Business Unit.Commercial Banking"
    bu_insurance          = "Business Unit.Insurance"
    gold                  = "Data Layer.Gold"

    # Used by the HR framework.
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

  # Identifiers apply tags (keys from local.tags) to matching columns. These
  # match the Harbourstone column names, in bronze, silver and gold.
  # `domain = null` makes a tenant-wide reference identifier; set it to a key
  # from local.domains to create the identifier inside that domain.
  identifiers = {
    # Names and dates of birth are masked unless a user is approved to see
    # them (see policies/data-mask-names-dob.yaml).
    name = {
      name        = "Person name columns"
      description = "Columns that hold a person's name"
      type        = "columnNameRegex"
      regex       = "^(first_name|last_name|full_name|cardholder_name|payee_name)$"
      tags        = ["pii_name"]
      domain      = null
    }

    date_of_birth = {
      name        = "Date of birth columns"
      description = "Columns that hold a date of birth"
      type        = "columnNameRegex"
      regex       = "^date_of_birth$"
      tags        = ["pii_date_of_birth"]
      domain      = null
    }

    contact_details = {
      name        = "Contact detail columns"
      description = "Columns that hold an email address, phone number or street address"
      type        = "columnNameRegex"
      regex       = "^(email|phone|mobile_phone|address_line)$"
      tags        = ["pii_contact_details"]
      domain      = null
    }

    government_id = {
      name        = "Government ID columns"
      description = "Columns that hold a tax file number, passport, driver licence or Medicare number"
      type        = "columnNameRegex"
      regex       = "^(tax_file_number|document_number|drivers_licence_number)$"
      tags        = ["pii_government_id"]
      domain      = null
    }

    financial_account = {
      name        = "Financial account columns"
      description = "Columns that hold a card number, BSB, account number or IBAN"
      type        = "columnNameRegex"
      regex       = "^(card_number|bsb|account_number|iban|payee_bsb|payee_account_number)$"
      tags        = ["pii_financial_account"]
      domain      = null
    }

    # Every silver and gold table has a `region` column (APAC, EMEA or AMER),
    # which the row-level policy compares with the user's Region attribute.
    region = {
      name        = "Region columns"
      description = "Columns that hold the region (APAC, EMEA or AMER) a row belongs to"
      type        = "columnNameRegex"
      regex       = "^region$"
      tags        = ["region"]
      domain      = null
    }

    # Created directly inside the Insurance domain: insured vehicles.
    insurance_vehicle = {
      name        = "Vehicle identifier columns"
      description = "Columns that hold a vehicle VIN or registration"
      type        = "columnNameRegex"
      regex       = "^(vin|registration)$"
      tags        = ["pii_government_id"]
      domain      = "insurance"
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
        # so no profile ID is hard-coded. Data policies are turned on for the
        # Harbourstone catalog only, in data_objects.tf.
        dataObjectDefaults = {
          syncPolicy = false
        }
      }
    }

    # Vitalis Health and Forgeline Industries operational data. Run the
    # connection's setup script in Snowflake first (the Immuta user, role and
    # key pair); the Immuta API does not accept passwords for Snowflake.
    # Cannot be updated in place: host, port, immutaSystemDatabase.
    snowflake = {
      technology = "Snowflake"

      credential = {
        authenticationType = "UnencryptedKeyPair"
        username           = var.snowflake_username
      }

      configuration = {
        clientConfiguration = {
          host                 = var.snowflake_host
          port                 = 443
          warehouse            = var.snowflake_warehouse
          role                 = var.snowflake_role
          immutaSystemDatabase = "IMMUTA_STU_J"
        }
        auditConfiguration = {
          enabled = false
        }
        dataObjectSync = {
          enabled   = true
          startTime = 0
          schedule  = "EVERY_24_HOURS"
        }
        syncOnCreate = true
        dataObjectDefaults = {
          syncPolicy = false
        }
      }
    }

    # HR data for every company (database hr). Cannot be updated in place:
    # host, port, immutaSystemDatabase.
    redshift = {
      technology = "Redshift"

      credential = {
        authenticationType = "UsernamePassword"
        username           = var.redshift_username
      }

      configuration = {
        clientConfiguration = {
          host                 = var.redshift_host
          port                 = 5439
          sslMode              = "REQUIRE"
          immutaSystemDatabase = "immuta_stu_j"
        }
        dataObjectSync = {
          enabled   = true
          startTime = 0
          schedule  = "EVERY_24_HOURS"
        }
        syncOnCreate = true
        dataObjectDefaults = {
          syncPolicy = false
        }
      }
    }
  }

  # The people in DEMO.md. In the demo their attributes come from Entra; here
  # they are set directly so the story can be replayed with Terraform.
  users = {
    # New analytics employee. The Analytics group gives her baseline access;
    # her Region limits the rows she sees, and PII is masked.
    cassandra = {
      user_id     = "cassandra.lee@example.com"
      name        = "Cassandra Lee"
      email       = "cassandra.lee@example.com"
      permissions = []

      # Attribute name => list of values.
      attributes = {
        Region = ["APAC"]

        # Brian's approval of unmasked names and dates of birth. Uncomment to
        # play that part of the demo.
        # "PII Access" = ["Names and Dates of Birth"]
      }
    }

    # Manager. His BusinessUnit decides which business's data he sees: change
    # it to "Retail Banking" and his access moves, with no policy change.
    brian = {
      user_id     = "brian.walsh@example.com"
      name        = "Brian Walsh"
      email       = "brian.walsh@example.com"
      permissions = []

      attributes = {
        BusinessUnit = ["Insurance"]
        Region       = ["APAC"]
      }
    }

    # CEO. The Executives group entitles her to gold (business insight)
    # tables only, with no standing access to raw data.
    alice = {
      user_id     = "alice.morgan@example.com"
      name        = "Alice Morgan"
      email       = "alice.morgan@example.com"
      permissions = []

      attributes = {
        Region = ["APAC", "EMEA", "AMER"]
      }
    }
  }

  # Group names are used in policies/ subscription policies.
  groups = {
    analytics = {
      name        = "Analytics"
      description = "Harbourstone analytics team"
      email       = "analytics@example.com"

      # Keys from local.users.
      members = ["cassandra"]

      # Attribute name => value.
      attributes = {
        Department = "Analytics"
      }
    }

    executives = {
      name        = "Executives"
      description = "Harbourstone executive team"
      email       = "executives@example.com"
      members     = ["alice"]

      attributes = {
        Department = "Executive"
      }
    }
  }
}
