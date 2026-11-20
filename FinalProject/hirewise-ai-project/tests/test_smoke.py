import os

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-do-not-use-in-production")

from app import create_app


def test_home_redirects_to_login():
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    response = app.test_client().get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_login_page_renders():
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    response = app.test_client().get("/login")
    assert response.status_code == 200
    assert b"HireWise AI" in response.data


def test_all_templates_parse():
    app = create_app()
    with app.app_context():
        for template_name in app.jinja_env.list_templates():
            app.jinja_env.get_template(template_name)


def test_required_blueprint_endpoints_exist():
    app = create_app()
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    required = {
        "auth.login", "auth.register", "auth.profile", "admin.dashboard",
        "admin.users", "admin.activity_log", "admin.vacancies",
        "recruiter.dashboard", "vacancies.vacancy_list",
        "candidates.candidate_list", "interviews.interview_list",
        "followups.followup_list", "offer_letters.preview_offer_letter",
        "ai.extract_profile", "ai.analyze_evidence",
        "ai.create_interview_questions", "interviews.complete_interview",
    }
    assert required.issubset(endpoints)
