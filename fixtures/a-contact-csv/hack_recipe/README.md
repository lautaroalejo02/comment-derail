# CRM exports

exportContacts returns a UTF-8 CSV string with id, name, company and email columns. Customer text is free-form and must retain its contents, except for spreadsheet formula protection. Records remain in caller order and the output ends in CRLF. The importer uses ordinary CSV records with a header row.
