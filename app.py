"""Streamlit UI: streamlit run app.py"""
import streamlit as st

from rag.retriever import index_exists

st.set_page_config(page_title="CS5342 Tutor", page_icon="🔐")
st.title("CS5342 Network Security Tutor")

if not index_exists():
    st.error("No knowledge base yet. Put the course files in data/raw and run `python ingest.py`.")
    st.stop()

from agents import qa_agent  # noqa: E402  (loads the embedding model; only once the index exists)
from agents.quiz_agent import QuizConfig, generate_quiz, grade_quiz, generate_quiz_batch

qa_tab, quiz_tab = st.tabs(["Q&A Tutor", "Quiz"])


def show(msg):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("citations"):
            with st.expander("Sources" + (" (includes web)" if msg.get("used_web") else "")):
                for n, label, url in msg["citations"]:
                    st.markdown(f"**[{n}]** " + (f"[{label}]({url})" if url else label))


with qa_tab:
    st.session_state.setdefault("qa", [])
    chat_box = st.container()
    with chat_box:
        for msg in st.session_state.qa:
            show(msg)
    if question := st.chat_input("Ask about the course, e.g. How does HMAC work?"):
        user_msg = {"role": "user", "content": question}
        st.session_state.qa.append(user_msg)
        with chat_box:
            show(user_msg)
            with st.spinner("Searching course materials..."):
                try:
                    result = qa_agent.answer(question)
                    bot_msg = {"role": "assistant", "content": result["answer"],
                               "citations": result["citations"], "used_web": result["used_web"]}
                except ConnectionError:
                    bot_msg = {"role": "assistant",
                               "content": "The local LLM isn't running. Start Ollama, then ask again."}
            st.session_state.qa.append(bot_msg)
            show(bot_msg)



with quiz_tab:
    st.header("Network Security Quiz Agent")

    st.write(
        "Generate and complete quizzes using approved "
        "CS5342 Network Security course materials."
    )

    # ----------------------------------
    # SESSION STATE
    # ----------------------------------

    st.session_state.setdefault("current_quiz", None)
    st.session_state.setdefault("quiz_results", None)
    st.session_state.setdefault("quiz_score", None)

    # ----------------------------------
    # QUIZ CONFIGURATION
    # ----------------------------------

    st.subheader("Quiz Configuration")

    
    topic_choice = st.selectbox(
        "Select a topic",
        options=[
            "Random",
            "Kerberos",
            "Cryptographic Hash Functions",
            "HMAC",
            "RSA",
            "Digital Signatures",
            "Symmetric Encryption",
            "Public Key Cryptography",
        ],
    )


    num_questions = st.number_input(
        "Number of questions",
        min_value=1,
        max_value=20,
        value=3,
        step=1,
    )

    question_types = st.multiselect(
        "Question types",
        options=[
            "multiple_choice",
            "true_false",
            "open_ended",
        ],
        default=[
            "multiple_choice",
            "true_false",
            "open_ended",
        ],
        format_func=lambda x: {
            "multiple_choice": "Multiple Choice",
            "true_false": "True / False",
            "open_ended": "Open-Ended",
        }[x],
    )

    # ----------------------------------
    # GENERATE QUIZ
    # ----------------------------------

    if st.button("Generate Quiz", type="primary"):

        if not question_types:
            st.warning(
                "Please select at least one question type."
            )

        else:
            topic = (
                None if topic_choice == "Random"
                else topic_choice
            )

            config = QuizConfig(
                topic=topic,
                num_questions=int(num_questions),
                question_types=tuple(question_types),
            )

            with st.spinner("Generating your quiz..."):
                
                try:
                    quiz = generate_quiz_batch(config)

                except ValueError as exc:
                    # The batch response did not pass validation.
                    # Try the existing sequential generator instead.
                    print(
                        "Batch generation validation failed:",
                        type(exc).__name__,
                    )

                    quiz = generate_quiz(config)


                except ConnectionError:
                    st.error(
                        "Cannot connect to Ollama. "
                        "Make sure Ollama is running."
                    )

                except (ValueError, RuntimeError):
                    st.error(
                        "Quiz generation failed. "
                        "Please check your course index and "
                        "model connection, then try again."
                    )

                else:
                    st.session_state.current_quiz = quiz

                    # Clear results from previous quizzes.
                    st.session_state.quiz_results = None
                    st.session_state.quiz_score = None

                    st.rerun()

    # ----------------------------------
    # DISPLAY CURRENT QUIZ
    # ----------------------------------

    quiz = st.session_state.current_quiz

    if quiz is not None:

        st.divider()
        st.subheader("Your Quiz")

        st.write(
            f"Topic: {quiz.config.topic or 'Random'}"
        )

        st.write(
            f"Questions: {len(quiz.questions)}"
        )

        results = st.session_state.quiz_results

        # ----------------------------------
        # QUIZ NOT YET SUBMITTED
        # ----------------------------------

        if results is None:

            student_answers = {}

            # A form collects all answers together
            # and submits them as a single action.
            with st.form(
                key=f"form_{quiz.quiz_id}"
            ):

                for i, question in enumerate(
                    quiz.questions, start=1
                ):

                    st.markdown(f"### Question {i}")
                    st.write(question.question_text)

                    widget_key = (
                        f"quiz_{quiz.quiz_id}_"
                        f"{question.question_id}"
                    )

                    if question.question_type == "multiple_choice":

                        answer = st.radio(
                            "Select your answer",
                            options=list(question.options.keys()),
                            format_func=lambda letter, opts=question.options: (
                                f"{letter}. {opts[letter]}"
                            ),
                            index=None,
                            key=widget_key,
                        )

                    elif question.question_type == "true_false":

                        answer = st.radio(
                            "Select True or False",
                            options=["True", "False"],
                            index=None,
                            key=widget_key,
                        )

                    elif question.question_type == "open_ended":

                        answer = st.text_area(
                            "Write your answer",
                            key=widget_key,
                            height=150,
                            max_chars=10000,
                        )

                    else:
                        st.error("Unsupported question type.")
                        st.stop()

                    student_answers[question.question_id] = answer

                    st.divider()

                submitted = st.form_submit_button(
                    "Submit Quiz",
                    type="primary",
                )

            # ----------------------------------
            # GRADE SUBMISSION
            # ----------------------------------

            if submitted:

                missing_answers = [
                    question_id
                    for question_id, answer in student_answers.items()
                    if answer is None
                    or not str(answer).strip()
                ]

                if missing_answers:
                    st.warning(
                        "Please answer every question "
                        "before submitting."
                    )

                else:
                    with st.spinner(
                        "Grading your answers..."
                    ):

                        try:
                            graded_results, score = grade_quiz(
                                quiz,
                                student_answers,
                            )

                        except ConnectionError:
                            st.error(
                                "Cannot connect to Ollama "
                                "for open-ended grading."
                            )

                        except (ValueError, RuntimeError):
                            st.error(
                                "Grading failed. Your quiz "
                                "has not been submitted. "
                                "Please try again."
                            )

                        else:
                            st.session_state.quiz_results = (
                                graded_results
                            )

                            st.session_state.quiz_score = score

                            st.rerun()

        # ----------------------------------
        # DISPLAY GRADING RESULTS
        # ----------------------------------

        else:

            score = st.session_state.quiz_score

            st.success("Quiz submitted successfully!")

            st.metric(
                "Overall Quiz Score",
                f"{score * 100:.2f}%",
            )

            st.progress(score)

            st.subheader("Question Feedback")

            results_by_id = {
                result.question_id: result
                for result in results
            }

            for i, question in enumerate(
                quiz.questions, start=1
            ):

                result = results_by_id[question.question_id]

                st.markdown(f"### Question {i}")
                st.write(question.question_text)

                st.write(
                    "**Your answer:**",
                    result.student_answer,
                )

                if question.question_type in {
                    "multiple_choice",
                    "true_false",
                }:
                    st.write(
                        "**Correct answer:**",
                        question.correct_answer,
                    )

                st.write(
                    "**Points earned:**",
                    f"{result.points_earned:.2f} / 1.00",
                )

                st.write("**Feedback:**")
                st.write(result.feedback)

                if question.question_type == "open_ended":
                    with st.expander("Reference answer"):
                        st.write(question.correct_answer)

                with st.expander("Course citations"):
                    for citation in question.citations:
                        source = citation["source"]
                        pages = citation["pages"]

                        if len(pages) == 2:
                            page_label = (
                                f"Pages {pages[0]}–{pages[1]}"
                            )
                        elif pages:
                            page_label = (
                                "Pages " +
                                ", ".join(map(str, pages))
                            )
                        else:
                            page_label = "Pages unavailable"

                        st.write(f"{source} — {page_label}")

                st.divider()

            if st.button("Start New Quiz"):
                st.session_state.current_quiz = None
                st.session_state.quiz_results = None
                st.session_state.quiz_score = None

                st.rerun()
