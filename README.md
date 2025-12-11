# 🧠 ADAM: AI-based Dynamic Assessment Module

**ADAM** is a powerful, dynamic web application built with **Flask** that revolutionizes the assessment process. It automatically generates customizable, AI-based quizzes from uploaded educational documents or user-provided topics. It features temporary IDs for secure, time-bound access for teachers and students, and provides automated, downloadable mark sheets.
**Access Website Here**: https://theadamproject.pythonanywhere.com/

---

## ✨ Key Features

* **Dynamic Quiz Generation:** Creates unique, challenging quizzes using the **OpenRouter API** based on uploaded documents or specific topics.
* **Time-Bound Teacher IDs:** Generates a temporary **50-minute** teacher ID for setting up and managing a new assessment session.
* **Unique Quiz IDs:** Each quiz session is assigned a unique Quiz ID that students use to access and attempt the assessment.
* **Secure Student Attempt:** Students can attempt the quiz using the generated Quiz ID.
* **Automated Mark Sheet:** Teachers can easily download the comprehensive mark sheet (CSV/XLSX) for the assessment session.
* **Database:** Uses **SQLite** for lightweight, file-based data storage.

---

## 🚀 Getting Started

Follow these steps to get a local copy of ADAM up and running on your machine.

### Prerequisites

* Python 3.8+
* **uv** package manager (installed via `pip install uv`)
* add .env with OPENROUTER_API_KEY variable

### Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/YourUsername/ADAM.git](https://github.com/YourUsername/ADAM.git)
    cd ADAM
    ```

2.  **Install dependencies using uv:**
    ```bash
    uv install -r requirements.txt
    ```

3.  **Configure OpenAI API Key:**
    * ADAM requires access to the OpenAI API for quiz generation.
    * Create a file named `.env` in the root directory and add your key:
        ```
        OPENROUTER_API_KEY="YOUR_API_KEY" 
        ```
    * *Note: Ensure your `requirements.txt` includes the `openai` and `python-dotenv` packages.*

4.  **Run the application:**
    ```bash
    uv run ADAM.py
    ```
    The app will be accessible at `http://127.0.0.1:5000/`.

---

## 🧑‍🏫 How to Use

### 1. Teacher Setup

1.  Click "**Generate Teacher ID**" (This ID is valid for 15 minutes).
2.  Use the ID to access the **Quiz Creation** interface.
3.  **Upload a document** or **Insert a topic** for the quiz content.
4.  Click "**Generate Quiz**." The content is processed by OpenAI.
5.  Share the generated **Quiz ID** with students.

### 2. Student Assessment

1.  Students enter the provided **Quiz ID** on the homepage.
2.  They attempt the quiz and submit their answers.

### 3. Downloading Results

1.  The teacher uses their **Teacher ID** to access the management interface.
2.  Select the desired **Quiz ID**.
3.  Click "**Download Mark Sheet**" to save the results spreadsheet.

---

## ⚙️ Technology Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Backend Framework** | **Flask** | Lightweight Python web framework. |
| **Package Manager** | **uv** | Fast, modern package installer and resolver. |
| **AI Integration** | **OpenAI API** (`openai` package) | Used for dynamic quiz content generation. |
| **Database** | **SQLite** | Local, file-based database for persistence. |
| **Frontend** | **HTML, CSS, Jinja2** | Standard web components and Flask templating. |

---

## 🤝 Contributing

Contributions are greatly appreciated. Please follow the standard GitHub fork and pull request workflow.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'feat: Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

---

## 📄 License

Distributed under the Apache License. See `LICENSE` for more information.

---

## 📧 Contact

will be available soon.



