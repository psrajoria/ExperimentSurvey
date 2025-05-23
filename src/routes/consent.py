from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import uuid
from datetime import datetime
from models import db, UserConsent, Response
from utilis import get_client_ip, get_user_agent, generate_unique_participant_id
import logging
from flask import Flask, request, render_template
from flask_session import Session
from flask_session_captcha import FlaskSessionCaptcha

main_bp = Blueprint("main", __name__)


@main_bp.route("/consent", methods=["GET"])
def consent():
    ip = get_client_ip()
    user_agent = get_user_agent()
    consent_record = UserConsent.query.filter_by(
        ip_address=ip, user_agent=user_agent
    ).first()

    if consent_record and consent_record.consent_given:
        return redirect(url_for("main.index"))  # Redirect if already consented

    return render_template("consent.html")


@main_bp.route("/give_consent", methods=["POST"])
def give_consent():
    """Processes user consent."""
    consent_status = request.form.get("consent")
    if consent_status == "accepted":
        ip = get_client_ip()
        user_agent = get_user_agent()
        consent_id = str(uuid.uuid4())

        consent_record = UserConsent(
            consent_id=consent_id,
            ip_address=ip,
            user_agent=user_agent,
            consent_given=True,
        )
        db.session.add(consent_record)
        db.session.commit()

        session["consent_id"] = consent_id
        return redirect(url_for("main.index"))  # Proceed to index
    elif consent_status == "denied":
        return redirect(url_for("main.exit"))  # Redirect to exit page
    else:
        flash("Please select an option to proceed.")
        return redirect(url_for("main.consent"))


@main_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


# Exit page
@main_bp.route("/exit", methods=["GET", "POST"])
def exit():
    return render_template("exit.html")


@main_bp.route("/index", methods=["GET", "POST"])
def index():
    error = None
    ip = get_client_ip()
    user_agent = get_user_agent()

    # Check if user has already given consent
    consent_record = UserConsent.query.filter_by(
        ip_address=ip, user_agent=user_agent
    ).first()

    if not consent_record or not consent_record.consent_given:
        return redirect(url_for("main.consent"))

    # Check if there's an existing response for this user
    response_record = Response.query.filter_by(
        consent_id=consent_record.consent_id
    ).first()

    if response_record:
        # Resume from last recorded point
        session["participant_id"] = response_record.participant_id
        session["start_time"] = response_record.start_time
        session["question_answered"] = True  # Assume they answered correctly before

        if response_record.completed:
            error = "You have already completed this survey."
            return render_template("index.html", error=error)

        return redirect(
            url_for("survey_bp.instructions")
        )  # Resume from where they left off

    # Handling the understanding question
    if request.method == "POST" and not error:
        answer = request.form.get("answer")
        if answer != "correct":
            error = "Incorrect answer. Please select the correct option to proceed."
        else:
            # Generate a new participant ID if no existing record
            participant_id = generate_unique_participant_id()
            session["participant_id"] = participant_id
            session["start_time"] = datetime.now()
            session["question_answered"] = True

            # Create a new response record
            response_record = Response(
                consent_id=consent_record.consent_id,
                participant_id=participant_id,
                completed=False,
                start_time=datetime.now(),
            )
            db.session.add(response_record)
            db.session.commit()

            return redirect(url_for("survey_bp.instructions"))  # Redirect to survey

    return render_template("index.html", error=error)
