-- Read-only role for Cura's SuperShyft connection (production readiness plan, 1.3).
-- Run as a SuperShyft database owner. Replace the password via your secret manager;
-- never commit a real value. Cura's SUPERSHYFT_DATABASE_URL must use this role.

CREATE ROLE cura_readonly LOGIN PASSWORD :'cura_readonly_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION CONNECTION LIMIT 20;

ALTER ROLE cura_readonly SET default_transaction_read_only = on;
ALTER ROLE cura_readonly SET statement_timeout = '5s';
ALTER ROLE cura_readonly SET idle_in_transaction_session_timeout = '10s';

REVOKE ALL ON SCHEMA public FROM cura_readonly;
GRANT USAGE ON SCHEMA public TO cura_readonly;

-- Grant SELECT only on the tables Cura reads. Keep this list in step with the queries
-- in integrations/supershyft/ and review it whenever a query is added.
GRANT SELECT ON public.assessment_instances TO cura_readonly;
GRANT SELECT ON public.assessment_packages TO cura_readonly;
GRANT SELECT ON public.diagnostic_package TO cura_readonly;
GRANT SELECT ON public.diagnostic_package_test_groups TO cura_readonly;
GRANT SELECT ON public.diagnostic_test_group_tests TO cura_readonly;
GRANT SELECT ON public.diagnostic_test_groups TO cura_readonly;
GRANT SELECT ON public.engagement_participants TO cura_readonly;
GRANT SELECT ON public.health_parameters TO cura_readonly;
GRANT SELECT ON public.individual_health_report TO cura_readonly;
GRANT SELECT ON public.participant_blood_bookings TO cura_readonly;
GRANT SELECT ON public.questionnaire_definitions TO cura_readonly;
GRANT SELECT ON public.questionnaire_options TO cura_readonly;
GRANT SELECT ON public.questionnaire_responses TO cura_readonly;
GRANT SELECT ON public.user_preferences TO cura_readonly;
GRANT SELECT ON public.users TO cura_readonly;

-- Verify: both statements must fail when connected as cura_readonly.
--   CREATE TABLE cura_write_probe(id int);
--   INSERT INTO public.users DEFAULT VALUES;
