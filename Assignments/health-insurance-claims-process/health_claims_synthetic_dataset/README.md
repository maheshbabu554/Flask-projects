# Synthetic Health Claims Data

Every person, hospital, policy, and claim in these CSV files is fictional. No real patient data or policy terms are included. All amounts are INR and business rules are invented for the classroom simulator. Do not treat any outcome as an actual insurance decision.

Import order: hospitals, plans, users, policies, members, claims, claim_documents, claim_history, settlements. Empty CSV cells mean NULL, not an empty string for numeric or date columns. Create password hashes locally for demo users; never store a shared plaintext password or import CSV username as an authentication secret. The application should generate status events for new actions rather than modifying the supplied history rows. Historic seed actors are placeholders and should be mapped to appropriate local demo accounts during import.

Relationships: users.hospital_id -> hospitals; policies.holder_user_id -> users; policies.plan_id -> plans; members.policy_id -> policies; claims.policy_id -> policies; claims.member_id -> members; claims.hospital_id -> hospitals; claims.officer_user_id -> users; documents/history/settlements.claim_id -> claims. Enforce that the claim member belongs to its selected policy and a hospital user's hospital_id matches the claim hospital_id.

Cases to demonstrate: 1001 paid; 1002 treatment type outside Essential Care coverage; 1003 approved cashless; 1005 missing document; 1006 expired policy; 1007 submitted and unassigned; 1011 and 1012 potential duplicate event; 1013 draft future admission (reject submission until date is valid). Case 1004 is in review. Cases 1002/1006 are preexisting rejected examples; students should not automatically reject real claims based on these examples.

For a cashless claim the hospital must be network-listed in this simulator. Reimbursement may use either network or non-network hospital. This is a classroom rule. A cashless approved amount is recorded as payable to the hospital; reimbursement to the policyholder. No real payment is processed.

Suggested local demo credential setup: create accounts with Werkzeug generate_password_hash for a password entered at seeding time; do not ship password hashes with this dataset.
