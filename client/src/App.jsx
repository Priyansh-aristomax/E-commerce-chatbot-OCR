import React, { useState, useRef, useEffect } from "react";
import ChatbotIcon from "./Components/ChatboxIcon";
import Chatform from "./Components/Chatform";
import Chatmessage from "./Components/Chatmessage";
import logo from "./assets/logo.png";
import "./index.css";
import { v4 as uuidv4 } from "uuid";

const App = () => {
  const [chathistory, setChathistory] = useState(() => {
    const savedHistory = sessionStorage.getItem("chatHistory");
    return savedHistory ? JSON.parse(savedHistory) : [];
  });
  const [showchatbot, setShowchatbot] = useState(false);
  const [productDescription, setProductDescription] = useState(null);
  const [hasFileAttached, setHasFileAttached] = useState(false);
  const [sessionId] = useState(() => {
    const savedSession = sessionStorage.getItem("chatSessionId");
    return savedSession || uuidv4();
  });
  const chatBodyRef = useRef();
  const maxHistoryLength = 20;

  useEffect(() => {
    sessionStorage.setItem("chatHistory", JSON.stringify(chathistory));
    sessionStorage.setItem("chatSessionId", sessionId);
  }, [chathistory, sessionId]);

  useEffect(() => {
    if (chatBodyRef.current) {
      chatBodyRef.current.scrollTo({
        top: chatBodyRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [chathistory]);

const generateBotResponse = async (history, descriptionOverride = null) => {
  // ✅ Use descriptionOverride if passed, else productDescription (only once), else last user text
  let prompt;
  if (descriptionOverride) {
    prompt = descriptionOverride;
  } else if (productDescription) {
    prompt = productDescription;
    setProductDescription(null); // reset so it won't override text-only queries
  } else {
    prompt = history[history.length - 1].text;
  }
  const updateHistory = (text, images = [], prices = []) => {
    setChathistory((prev) => {
      const newHistory = [
        ...prev.filter((msg) => msg.text !== "Thinking..."),
        { from: "model", text, image: images, price: prices, sessionId },
      ].slice(-maxHistoryLength);
      return newHistory;
    });
  };

  try {
    const formattedHistory = history.slice(0, -1).map((msg) => ({
      role: msg.from === "user" ? "user" : "assistant",
      content: msg.text,
    }));

    const response = await fetch("http://localhost:8000/generate-response", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        chat_history: formattedHistory,
        session_id: sessionId,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      updateHistory("Error: " + (errorData.detail || "Unknown error occurred."));
      return;
    }

    const data = await response.json();
    const images = data.products?.map((p) => p.image) || [];
    const prices = data.products?.map((p) => p.price) || [];
    updateHistory(data.response, images, prices);
  } catch (error) {
    console.error("Fetch/network error:", error);
    updateHistory("Sorry, the chatbot is unavailable due to a network error.");
  }
};

  const handleFileAndMessage = async (file, usermessage = "") => {
    // Handle text-only messages
    if (!file) {
      if (!usermessage || usermessage.trim() === "") {
        console.log("❌ Empty message - not processing");
        return;
      }
      const userMessageObj = {
        from: "user",
        text: usermessage.trim(),
        sessionId,
      };

      setChathistory((prev) => [
        ...prev,
        userMessageObj,
        { from: "model", text: "Thinking...", sessionId },
      ]);

      generateBotResponse([...chathistory, userMessageObj]);
      return;
    }

    // Handle file uploads
    setHasFileAttached(true);

    // Create image URL for preview if it's an image
    const imageUrl = file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined;

    // ALWAYS add user message with uploaded file to chat history FIRST
    const userMessageObj = {
      from: "user",
      text: usermessage && usermessage.trim(), //? usermessage.trim() : `Uploaded: ${file.name}`, // 🔧 FIX: Show text OR filename
      image: imageUrl ? [imageUrl] : undefined,
      // filename: file.name,
      sessionId,
    };

    // Add user message immediately
    setChathistory((prev) => [
      ...prev,
      userMessageObj,
      { from: "model", text: "Thinking...", sessionId },
    ]);

    try {
      // Create FormData for file upload
      const formData = new FormData();
      formData.append("file", file);

      // Make API call
      const response = await fetch("http://localhost:8000/upload-file", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      // Remove "Thinking..." message and add bot response
      setChathistory((prev) => {
        const filtered = prev.filter((msg) => msg.text !== "Thinking...");
        
        let botMessage = {
          from: "model",
          text: "",
          image: [],
          price: [],
          sessionId
        };

        if (data.success) {
          // File is relevant to clothes - show the generated description and products
          let responseText = "";
          
          // Add the generated description from the API
          if (data.generated_description) {
            responseText = `Based on your image, I found: ${data.generated_description}`;
          }
          
          // Add product recommendations info
          if (data.recommended_products && data.recommended_products.length > 0) {
            responseText += responseText ? "\n\nHere are some matching products:" : "Here are some matching products:";
            botMessage.image = data.recommended_products.map(product => product.image || product.image_url).filter(Boolean);
            botMessage.price = data.recommended_products.map(product => product.price || "N/A");
          } else {
            responseText += responseText ? "\n\nI couldn't find matching products at the moment." : "I found that your image is related to clothing, but I couldn't find matching products at the moment.";
          }
          
          botMessage.text = responseText || "Here are some recommendations based on your image:";
          
          // Set product description for context
          setProductDescription(data.generated_description);
        } else {
          // File is NOT relevant to clothes
          botMessage.text = data.message || "This image is not related to women's clothing. Please upload a clothing-related image.";
        }

        return [...filtered, botMessage].slice(-maxHistoryLength);
      });

    } catch (error) {
      console.error("Upload error:", error);
      
      // Remove "Thinking..." and add error message
      setChathistory((prev) => {
        const filtered = prev.filter((msg) => msg.text !== "Thinking...");
        return [
          ...filtered,
          {
            from: "model",
            text: "Sorry, there was an error processing your file. Please try again.",
            sessionId
          }
        ].slice(-maxHistoryLength);
      });
    } finally {
      setHasFileAttached(false);
    }
  };

  return (
    <div className={`container ${showchatbot ? "show-chatbot" : ""} ${hasFileAttached ? "has-file" : ""}`}>
      <div className="App">
        <header className="header-container">
          <div className="logo-section">
            <img src={logo} alt="AristoMax Logo" className="company-logo" />
            <h1 className="gradient-header">ShopBuddy</h1>
          </div>
          <div className="blue-bar"></div>
        </header>
        <main className="p-4"></main>
        <footer className="bg-gray-800 p-4 text-white text-center relative w-full top-[22rem]"
                style={{ fontFamily: "Poppins, sans-serif" }}>
        </footer>
      </div>

      <button onClick={() => setShowchatbot((prev) => !prev)} className="chatbot-toggler">
        <span className="material-symbols-outlined">chat</span>
        <span className="material-symbols-outlined">close</span>
      </button>

      <div className={`chatbot-popup ${hasFileAttached ? "has-file" : ""}`}>
        <div className="chat-header">
          <div className="header-info">
            <ChatbotIcon />
            <h1 className="logo-text">AristoMax - Chatbot</h1>
          </div>
          <button onClick={() => setShowchatbot((prev) => !prev)} className="material-symbols-outlined">
            keyboard_arrow_down
          </button>
        </div>

        <div ref={chatBodyRef} className="Chatbot-body">
          <br />
          <div className="message bot-message">
            <ChatbotIcon />
            <p className="message-text">Hello, <br /> How can I assist you?</p>
          </div>
          {chathistory.map((message, index) => (
            <Chatmessage
              key={`${message.sessionId || "initial"}-${index}`}
              role={message.from === "user" ? "user" : "model"}
              text={message.text}
              image={message.image}
              price={message.price}
              filename={message.filename}
            />
          ))}
        </div>

        <Chatform
          setchathistory={setChathistory}
          chathistory={chathistory}
          generateBotResponse={generateBotResponse}
          sessionId={sessionId}
          setProductDescription={setProductDescription}
          onFileSend={handleFileAndMessage}
          onFileAttachChange={setHasFileAttached}
        />
      </div>

      <footer className="footer">
        <div className="blue-bar-footer"></div>
        <p>© 2025 <b>Aristomax Technologies Pv. Ltd.</b>, All Right Reserved.</p>
      </footer>
    </div>
  );
};

export default App;