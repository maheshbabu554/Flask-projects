
"use strict";

/*
 * HireWise AI - Bulk Resume Upload
 * Generates candidate information fields for selected resumes.
 */

document.addEventListener("DOMContentLoaded", function () {

    const uploadForm = document.getElementById("bulk-upload-form");

    if (!uploadForm) {
        return;
    }

    const fileInput = document.getElementById("resumes");
    const fileList = document.getElementById("selected-files");
    const candidateDetails = document.getElementById("candidate-details");
    const submitButton = document.getElementById("upload-button");

    const MAX_FILES = 20;
    const MAX_SIZE = 5 * 1024 * 1024;

    function createCandidateFields(count) {

        candidateDetails.innerHTML = "";

        for (let i = 0; i < count; i++) {

            const entry = document.createElement("div");

            entry.className = "candidate-entry border rounded p-3 mb-3";

            entry.innerHTML = `
                <h6 class="fw-bold">Candidate ${i + 1}</h6>

                <div class="row g-3">

                    <div class="col-md-6">
                        <label class="form-label">
                            Full Name
                        </label>

                        <input
                            type="text"
                            class="form-control candidate-name"
                            name="candidate_names"
                            placeholder="Enter candidate name"
                            required
                        >
                    </div>

                    <div class="col-md-6">
                        <label class="form-label">
                            Email Address
                        </label>

                        <input
                            type="email"
                            class="form-control candidate-email"
                            name="candidate_emails"
                            placeholder="Enter candidate email"
                            required
                        >
                    </div>

                </div>
            `;

            candidateDetails.appendChild(entry);

        }

    }

    fileInput.addEventListener("change", function () {

        const files = Array.from(fileInput.files || []);

        const errors = [];

        fileList.innerHTML = "";
        submitButton.disabled = true;

        if (files.length > MAX_FILES) {
            errors.push("You can select a maximum of 20 resumes.");
        }

        files.forEach(function (file) {

            const extension = file.name
                .substring(file.name.lastIndexOf("."))
                .toLowerCase();

            if (![".pdf", ".docx"].includes(extension)) {
                errors.push(file.name + ": Only PDF and DOCX files are allowed.");
            }

            if (file.size === 0) {
                errors.push(file.name + ": The file is empty.");
            }

            if (file.size > MAX_SIZE) {
                errors.push(file.name + ": Maximum file size is 5 MB.");
            }

            const item = document.createElement("li");

            item.textContent =
                file.name + " (" +
                (file.size / (1024 * 1024)).toFixed(2) +
                " MB)";

            fileList.appendChild(item);

        });

        if (errors.length > 0) {

            alert(errors.join("\n"));

            fileInput.value = "";
            fileList.innerHTML = "";
            candidateDetails.innerHTML = "";

            return;
        }

        createCandidateFields(files.length);

        submitButton.disabled = files.length === 0;

    });

    uploadForm.addEventListener("submit", function (event) {

        const files = fileInput.files.length;

        const names = document.querySelectorAll(".candidate-name");
        const emails = document.querySelectorAll(".candidate-email");

        if (
            files === 0 ||
            names.length !== files ||
            emails.length !== files
        ) {

            event.preventDefault();

            alert("Please provide details for every selected resume.");

            return;
        }

        if (!uploadForm.reportValidity()) {
            event.preventDefault();
            return;
        }

        if (!window.confirm(
            "Are you sure you want to upload " + files + " resumes?"
        )) {
            event.preventDefault();
        }

    });

});
