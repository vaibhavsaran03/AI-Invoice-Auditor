import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

export const invoiceApi = {
  // 1. Send the PDF file to FastAPI
  uploadInvoice: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  // 2. Start the Agentic processing
  processInvoice: async (filename: string) => {
    const response = await apiClient.post(`/process/${filename}`);
    return response.data;
  },

  // 3. Natural Language Query (RAG)
  askAI: async (query: string) => {
    const response = await apiClient.post('/chat', { query });
    return response.data; // { answer, sources }
  },

  // 4. Get the list of paused invoices (HITL)
  getHitlQueue: async () => {
    const response = await apiClient.get('/hitl-queue');
    return response.data;
  },

  // 5. Get details for a specific paused thread
  getInvoiceDetails: async (threadId: string) => {
    const response = await apiClient.get(`/hitl-details/${threadId}`);
    return response.data;
  },

  // 6. Unified Action for Approve/Reject
  handleHitlAction: async (threadId: string, payload: { action: string, data: any, comment: string }) => {
    const response = await apiClient.post(`/hitl-action/${threadId}`, payload);
    return response.data;
  },

  // 🌟 NEW: Fetch persistent stats from SQLite (audit_history table)
  getAuditStats: async () => {
    const response = await apiClient.get('/audit-stats');
    return response.data; // Returns { approved: number }
  },

  // 🌟 NEW: Fetch rejection history from SQLite
  getRejectedHistory: async () => {
    const response = await apiClient.get('/rejected-history');
    return response.data; // Returns list of rejected objects
  }
};