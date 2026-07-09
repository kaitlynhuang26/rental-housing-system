import React, { useEffect, useState } from "react";
import { Bot, Check, Send, Trash2, User, X } from "lucide-react";
import { api } from "../api";
import { PageHeader } from "../components/Common";

const welcome = { role: "assistant", text: "Hi. Ask me about rooms and payments, or tell me about a change you want to make." };
const CHAT_STORAGE_KEY = "rental-chat-session-v2";
const CHAT_MEMORY_MS = 5 * 60 * 1000;

function loadChatSession() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(CHAT_STORAGE_KEY));
    if (saved && Date.now() - saved.savedAt < CHAT_MEMORY_MS) {
      return {
        messages: saved.messages?.length ? saved.messages : [welcome],
        pendingContext: saved.pendingContext || "",
      };
    }
  } catch {
    // Start a clean chat if saved browser data is invalid.
  }
  return { messages: [welcome], pendingContext: "" };
}

export default function Chatbot({ refresh }) {
  const initial = loadChatSession();
  const [messages, setMessages] = useState(initial.messages);
  const [pendingContext, setPendingContext] = useState(initial.pendingContext);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify({
      savedAt: Date.now(),
      messages,
      pendingContext,
    }));
  }, [messages, pendingContext]);

  const send = async (event) => {
    event?.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setMessages((items) => [...items, { role: "user", text }]);
    setSending(true);
    try {
      const followUpDetail = normalizeFollowUpAnswer(text);
      const combinedContext = pendingContext
        ? `${pendingContext}\nAdditional user information: ${followUpDetail}`
        : text;
      const apiMessage = pendingContext
        ? `${combinedContext}\nThis is one continuing request. Keep the original intent and combine all provided fields. Do not restart the task.`
        : text;
      const response = await api.chat(apiMessage);
      setPendingContext(response.type === "follow_up" ? combinedContext : "");
      setMessages((items) => [...items, { role: "assistant", text: response.message, response }]);
    } catch (error) {
      setMessages((items) => [...items, { role: "error", text: error.message }]);
    } finally { setSending(false); }
  };

  const confirm = async (actionId, shouldSave) => {
    setSending(true);
    try {
      const result = await api.confirmChat(actionId, shouldSave);
      setMessages((items) => [...items, { role: "assistant", text: result.message, saved: shouldSave }]);
      if (shouldSave && result.success) await refresh();
    } catch (error) {
      setMessages((items) => [...items, { role: "error", text: error.message }]);
    } finally { setSending(false); }
  };

  const clearChat = () => {
    setMessages([welcome]);
    setPendingContext("");
    sessionStorage.removeItem(CHAT_STORAGE_KEY);
  };

  return <>
    <PageHeader title="Chatbot" subtitle="Ask a question or preview a safe change to the rental records." action={
      <button className="button secondary" onClick={clearChat}><Trash2 size={17} />Clear chat</button>
    } />
    <section className="chat-panel">
      <div className="chat-messages">{messages.map((item, index) => <div className={`chat-message ${item.role}`} key={index}>
        <span className="avatar">{item.role === "user" ? <User size={18} /> : <Bot size={18} />}</span>
        <div className="bubble"><p>{item.text}</p>
          {item.response?.preview && <PreviewDetails preview={item.response.preview} />}
          {item.response?.type === "confirmation_required" && <div className="confirm-buttons">
            <button className="button primary" disabled={sending} onClick={() => confirm(item.response.action_id, true)}><Check size={17} />Confirm Save</button>
            <button className="button secondary" disabled={sending} onClick={() => confirm(item.response.action_id, false)}><X size={17} />Cancel</button>
          </div>}
        </div>
      </div>)}{sending && <div className="typing">Assistant is checking the records...</div>}</div>
      <form className="chat-input" onSubmit={send}><textarea rows="2" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type a message, for example: Which rooms are empty?" /><button className="button primary" disabled={!input.trim() || sending}><Send size={18} />Send</button></form>
    </section>
  </>;
}

function normalizeFollowUpAnswer(value) {
  const lower = value.trim().toLowerCase();
  if (
    lower.includes("not paid")
    || lower.includes("hasn't paid")
    || lower.includes("has not paid")
    || lower === "no payment"
  ) {
    return "The tenant has not paid yet. Set amount_paid to 0. Leave payment_date and payment_method blank; these are intentionally not required.";
  }
  return value;
}

function PreviewDetails({ preview }) {
  return <div className="preview-details">
    {!!preview.rows_to_create?.length && <div><strong>{preview.rows_to_create[0]?.backup_file ? "Workbook restoration" : "Rows to create"}</strong>{preview.rows_to_create.map((row, i) => <span key={i}>{row.backup_file ? `Restore ${row.backup_file} from ${row.backup_created_at}` : `Room ${row.room_id}: ${row.rent_start_date} to ${row.rent_end_date}`}</span>)}</div>}
    {!!preview.changes?.length && <div><strong>Proposed changes</strong>{preview.changes.slice(0, 8).map((change, i) => <span key={i}>Room row {change.row_index}: {change.column} → {String(change.new_value ?? "-")}</span>)}</div>}
    {!!preview.warnings?.length && <div><strong>Warnings</strong>{preview.warnings.map((warning) => <span key={warning}>{warning}</span>)}</div>}
  </div>;
}
