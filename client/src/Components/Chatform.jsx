import React, { useRef, useState } from "react";

const Chatform = ({
  chathistory,
  setchathistory,
  generateBotResponse,
  sessionId,
  setProductDescription,
  onFileSend,
  onFileAttachChange,
}) => {
  const inputRef = useRef();
  const fileInputRef = useRef();

  const [attachedFile, setAttachedFile] = useState(null);
  const [previewURL, setPreviewURL] = useState(null);

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
    alert("Please upload only image files");
    e.target.value = ""; // Clear the input
    return;
    }

    setAttachedFile(file);
    onFileAttachChange?.(true); // Notify parent that file is attached

    if (file.type.startsWith("image/")) {
      const imageUrl = URL.createObjectURL(file);
      setPreviewURL(imageUrl);
    } else {
      setPreviewURL(file.name);
    }
  };

  const handleformSubmit = async (e) => {
    e.preventDefault();
    const usermessage = inputRef.current.value.trim();
    if (!usermessage && !attachedFile) return;

    inputRef.current.value = "";
    inputRef.current.style.height = "auto";

    if (onFileSend) {
      onFileSend(attachedFile, usermessage);
    }

    setAttachedFile(null);
    setPreviewURL(null);
    onFileAttachChange?.(false); // Notify parent that file is removed
  };

  const handleInputChange = () => {
    const textarea = inputRef.current;
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
    textarea.style.overflowY =
      textarea.scrollHeight > 4.5 * 16 ? "auto" : "hidden";
  };

  const handleRemoveFile = () => {
    setAttachedFile(null);
    setPreviewURL(null);
    onFileAttachChange?.(false); // Notify parent that file is removed
  };

  return (
    <form className="chat-form" onSubmit={handleformSubmit}>
      {previewURL && (
        <div className="file-preview-container">
          {attachedFile?.type?.startsWith("image/") ? (
            <div className="preview-wrapper">
              <img src={previewURL} alt="preview" className="file-thumbnail" />
              <button
                type="button"
                className="remove-btn"
                onClick={handleRemoveFile}
              >
                X
              </button>
            </div>
          ) : (
            <div className="preview-wrapper non-image">
              <span className="file-thumbnail">📄 {attachedFile?.name}</span>
              <button
                type="button"
                className="remove-btn"
                onClick={handleRemoveFile}
              >
                X
              </button>
            </div>
          )}
        </div>
      )}

      <div className="input-row">
        <textarea
          ref={inputRef}
          placeholder="Type your query here..."
          className="message-input"
          rows="1"
          onInput={handleInputChange}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleformSubmit(e);
            }
          }}
        ></textarea>

        <div className="button-group">
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: "none" }}
            accept="image/*"
            onChange={handleFileChange}
          />
          <button
            type="button"
            className="material-symbols-outlined"
            onClick={() => fileInputRef.current.click()}
            title="Attach file"
          >
            attach_file
          </button>
          <button
            type="submit"
            className="material-symbols-outlined"
            title="Send"
          >
            send
          </button>
        </div>
      </div>
    </form>
  );
};

export default Chatform;