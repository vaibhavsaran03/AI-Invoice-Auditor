"use client";

import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { 
  Upload, MessageSquare, ShieldCheck, Activity, Send, Loader2, 
  AlertCircle, CheckCircle2, ChevronRight, Save, Database, 
  Search, FileCheck, XCircle 
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { invoiceApi } from '@/lib/api';
import { Toaster, toast } from 'sonner';

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<"dashboard" | "ingest" | "hitl" | "rejected">("dashboard");
  const [isProcessing, setIsProcessing] = useState(false);
  const [approvedCount, setApprovedCount] = useState(0); 
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<{ role: string, content: string }[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [hitlQueue, setHitlQueue] = useState<string[]>([]);
  const [rejectedHistory, setRejectedHistory] = useState<any[]>([]);
  const [selectedReview, setSelectedReview] = useState<any>(null);
  const [humanComment, setHumanComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 🌟 CHANGE THESE TO YOUR ACTUAL FILENAMES IN public/samples/
  const sampleFiles = [
    "test_invoice_match.pdf",
    "test_invoice_mismatch.pdf",
    "test_invoice.pdf"
  ];

  const refreshSystemState = async () => {
    try {
      const [hitl, rejected, stats] = await Promise.all([
        invoiceApi.getHitlQueue(),
        invoiceApi.getRejectedHistory(),
        invoiceApi.getAuditStats()
      ]);
      setHitlQueue(hitl.queue || []);
      setRejectedHistory(rejected || []);
      setApprovedCount(stats.approved || 0);
    } catch (err) { console.error("Sync Error"); }
  };

  useEffect(() => {
    refreshSystemState();
    const interval = setInterval(refreshSystemState, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleAuditAction = async (action: "approved" | "rejected") => {
    if (!selectedReview) return;
    setIsSubmitting(true);
    try {
      await invoiceApi.handleHitlAction(selectedReview.id, { action, data: selectedReview.data, comment: humanComment });
      toast.success(`Invoice ${action} and recorded in DB`);
      setSelectedReview(null);
      setHumanComment("");
      refreshSystemState();
    } catch (err) { toast.error("Action failed"); } finally { setIsSubmitting(false); }
  };

  const handleChat = async () => {
    if (!chatInput) return;
    const q = chatInput; setChatInput("");
    setMessages(prev => [...prev, { role: 'user', content: q }]);
    try {
      const data = await invoiceApi.askAI(q);
      setMessages(prev => [...prev, { role: 'assistant', content: data.answer }]);
    } catch (err) { toast.error("RAG Offline"); }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    executePipeline(file);
  };

  // 🌟 RE-ENGINEERED: This sends the ACTUAL file to your Extractor Agent
  const executePipeline = async (file: File) => {
    setIsProcessing(true);
    try {
      const uploadRes = await invoiceApi.uploadInvoice(file);
      const processRes = await invoiceApi.processInvoice(uploadRes.filename);
      if (processRes.status === "paused") {
        toast.warning(`Manual Review: ${file.name}`);
        setActiveTab("hitl");
      } else {
        toast.success(`Audit Complete: ${file.name}`);
        setActiveTab("dashboard");
      }
      refreshSystemState();
    } catch (err) { toast.error("Pipeline Error"); } finally { setIsProcessing(false); }
  };

  // 🌟 DYNAMIC FETCH: Grabs the real PDF from your public folder
  const handleSampleTest = async (fileName: string) => {
    try {
      const response = await fetch(`/samples/${fileName}`);
      if (!response.ok) throw new Error("404");
      const blob = await response.blob();
      const file = new File([blob], fileName, { type: "application/pdf" });
      executePipeline(file);
    } catch (err) {
      toast.error(`Sample ${fileName} not found in public/samples/`);
    }
  };

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 overflow-hidden font-sans">
      <Toaster position="top-right" richColors />
      
      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar { width: 8px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: #f1f5f9; border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
      `}</style>

      <aside className="w-64 bg-slate-950 text-white p-6 flex flex-col gap-8 shadow-xl z-20 shrink-0">
        <div className="flex items-center gap-3"><ShieldCheck className="text-blue-500" size={32} /><h1 className="text-xl font-bold tracking-tight">AI Auditor</h1></div>
        <nav className="flex flex-col gap-2">
          <Button variant={activeTab === "dashboard" ? "secondary" : "ghost"} className="justify-start gap-3 text-slate-300" onClick={() => setActiveTab("dashboard")}><Activity size={18} /> Dashboard</Button>
          <Button variant={activeTab === "ingest" ? "secondary" : "ghost"} className="justify-start gap-3 text-slate-300" onClick={() => setActiveTab("ingest")}><Upload size={18} /> Ingest Invoice</Button>
          <Button variant={activeTab === "hitl" ? "secondary" : "ghost"} className="justify-start gap-3 relative text-slate-300" onClick={() => setActiveTab("hitl")}><MessageSquare size={18} /> HITL Review {hitlQueue.length > 0 && <span className="absolute right-2 top-2 bg-red-500 text-white text-[10px] px-1.5 rounded-full animate-pulse">{hitlQueue.length}</span>}</Button>
          <Button variant={activeTab === "rejected" ? "secondary" : "ghost"} className="justify-start gap-3 text-slate-300" onClick={() => setActiveTab("rejected")}><XCircle size={18} /> Rejected</Button>
        </nav>
        <div className="mt-auto pt-6 border-t border-slate-800 flex justify-between text-sm px-2"><span className="text-slate-400 font-medium text-[10px] uppercase">Total Approved</span><span className="text-blue-500 font-mono font-bold">{approvedCount}</span></div>
      </aside>

      <main className="flex-1 flex flex-col min-h-0 overflow-hidden">
        {activeTab === "dashboard" && (
            <div className="flex flex-col h-full p-8 gap-6 overflow-hidden">
                <header className="shrink-0"><h2 className="text-3xl font-extrabold tracking-tight">Audit Terminal</h2></header>
                <div className={`shrink-0 bg-white border rounded-3xl p-6 flex justify-between items-center shadow-sm ${isProcessing ? 'opacity-100' : 'opacity-40'}`}>
                    {["Ingestion", "Extraction", "ERP Sync", "Final Audit"].map((l, i) => (
                        <React.Fragment key={i}>
                            <div className="flex flex-col items-center gap-1"><div className="p-2 rounded-full bg-slate-100"><Database size={16}/></div><span className="text-[10px] font-bold uppercase">{l}</span></div>
                            {i < 3 && <div className="flex-1 h-[2px] mx-4 bg-slate-200" />}
                        </React.Fragment>
                    ))}
                </div>
                <Card className="flex-1 flex flex-col min-h-0 border-none shadow-2xl bg-white rounded-3xl overflow-hidden">
                    <CardHeader className="bg-slate-50 border-b shrink-0 py-3 px-6"><CardTitle className="text-xs font-bold text-slate-400 flex items-center gap-2"><MessageSquare size={14}/> RAG Intelligence</CardTitle></CardHeader>
                    <div className="flex-1 overflow-y-auto custom-scrollbar p-6 bg-white">
                        <div className="max-w-4xl mx-auto space-y-6">
                        {messages.length === 0 && (
                            <div className="text-center text-slate-300 mt-20">
                            <ShieldCheck size={64} className="mx-auto opacity-10 mb-4" />
                            <p className="text-sm italic">Analyze your audited documents with natural language.</p>
                            </div>
                        )}
                        {messages.map((m, i) => (
                            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[85%] p-5 rounded-3xl text-sm border ${m.role === 'user' ? 'bg-blue-600 text-white border-blue-500 rounded-br-none' : 'bg-slate-50 text-slate-800 rounded-bl-none prose prose-slate max-w-none'}`}>
                                <div className={m.role === 'user' ? 'text-white' : 'text-slate-800'}><ReactMarkdown>{m.content}</ReactMarkdown></div>
                            </div>
                            </div>
                        ))}
                        <div ref={messagesEndRef} />
                        </div>
                    </div>
                    <div className="p-6 border-t shrink-0 bg-white">
                        <div className="max-w-4xl mx-auto flex gap-3 bg-slate-50 border-2 p-2 rounded-full items-center shadow-sm">
                        <input className="flex-1 px-4 py-2 text-sm outline-none bg-transparent" placeholder="Ask AI about invoices..." value={chatInput} onChange={e => setChatInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleChat()} />
                        <Button onClick={handleChat} size="icon" className="rounded-full bg-blue-600 h-10 w-10 shrink-0"><Send size={18}/></Button>
                        </div>
                    </div>
                </Card>
            </div>
        )}

        {activeTab === "ingest" && (
          <div className="flex h-full">
            <div className="flex-1 flex flex-col items-center justify-center border-r bg-white p-12 text-center">
              <div className="bg-blue-50 p-6 rounded-full mb-6"><Upload className="text-blue-600" size={48} /></div>
              <h2 className="text-2xl font-bold mb-2">Upload Own Invoice</h2>
              <p className="text-slate-500 mb-8 max-w-xs text-sm">Upload a PDF from your system to trigger the multi-agent pipeline.</p>
              <label className="cursor-pointer bg-blue-600 text-white px-10 py-4 rounded-full hover:bg-blue-700 shadow-xl font-bold transition-all flex items-center gap-2">
                <input type="file" onChange={handleFileUpload} className="hidden" disabled={isProcessing} />
                {isProcessing ? <Loader2 className="animate-spin" size={20} /> : <Upload size={20} />} Choose File
              </label>
            </div>

            <div className="flex-1 flex flex-col p-12 bg-slate-50 overflow-y-auto custom-scrollbar">
              <h2 className="text-2xl font-bold mb-2">Test Samples</h2>
              <p className="text-slate-500 mb-8 text-sm">Select a pre-loaded PDF to test specific audit logic.</p>
              <div className="space-y-4">
                {sampleFiles.map((fileName, i) => (
                  <Card key={i} className="p-5 bg-white border-slate-200 hover:shadow-md transition-all">
                    <div className="flex justify-between items-center gap-4">
                      <div className="text-left">
                        <p className="font-bold text-slate-900 truncate max-w-[180px]">{fileName}</p>
                        <p className="text-[10px] text-blue-600 font-mono tracking-tighter">PDF DEMO DATA</p>
                      </div>
                      <div className="flex gap-2 shrink-0">
                        <Button variant="outline" size="sm" onClick={() => window.open(`/samples/${fileName}`, '_blank')}><Search size={14} className="mr-1"/> View</Button>
                        <Button size="sm" className="bg-slate-900" onClick={() => handleSampleTest(fileName)} disabled={isProcessing}><FileCheck size={14} className="mr-1"/> Test</Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === "hitl" && (
          <div className="p-8 flex flex-col h-full gap-6 overflow-hidden">
             <h2 className="text-3xl font-extrabold tracking-tight">Manual Audit</h2>
             <div className="flex flex-1 gap-6 min-h-0 pb-6">
               <Card className="w-80 shadow-md bg-white shrink-0 overflow-hidden flex flex-col">
                 <div className="flex-1 overflow-y-auto custom-scrollbar">
                    {hitlQueue.length === 0 ? <div className="p-8 text-center text-slate-300 italic">Queue clear.</div> : 
                    hitlQueue.map(id => (
                      <button key={id} onClick={() => invoiceApi.getInvoiceDetails(id).then(d => setSelectedReview({id, ...d}))} className={`w-full text-left p-4 border-b ${selectedReview?.id === id ? 'bg-blue-50 border-r-4 border-r-blue-600' : ''}`}>
                        <p className="text-sm font-bold truncate">{id}</p>
                      </button>
                    ))}
                 </div>
               </Card>
               <Card className="flex-1 flex flex-col shadow-lg bg-white overflow-hidden">
                  <CardHeader className="bg-slate-900 text-white flex justify-between py-4 px-6 shrink-0">
                    <CardTitle className="text-xs uppercase font-bold tracking-widest">Auditor Workspace</CardTitle>
                    {selectedReview && <div className="flex gap-2"><Button size="sm" variant="destructive" onClick={() => handleAuditAction("rejected")}>Reject</Button><Button size="sm" className="bg-green-600" onClick={() => handleAuditAction("approved")}>Approve</Button></div>}
                  </CardHeader>
                  <CardContent className="flex-1 p-6 flex flex-col gap-4 overflow-hidden">
                    {selectedReview ? (<>
                      <div className="bg-amber-50 border border-amber-200 p-4 rounded-xl shrink-0"><h4 className="text-amber-800 font-bold text-xs flex items-center gap-2 mb-2"><AlertCircle size={14}/> SYSTEM DISCREPANCIES:</h4><ul className="text-xs text-amber-700 list-disc ml-4">{selectedReview.errors?.map((e:string, i:number) => <li key={i}>{e}</li>)}</ul></div>
                      <textarea className="flex-1 font-mono text-[11px] p-4 bg-slate-950 text-emerald-400 rounded-xl outline-none resize-none shadow-inner border border-slate-800" value={JSON.stringify(selectedReview.data, null, 2)} onChange={e => { try { setSelectedReview({...selectedReview, data: JSON.parse(e.target.value)}); } catch(x){} }} />
                      <input className="w-full bg-slate-50 border-2 p-3 rounded-xl text-sm" placeholder="Audit note for RAG..." value={humanComment} onChange={e => setHumanComment(e.target.value)} />
                    </>) : <div className="m-auto text-slate-300 italic">Select an invoice to begin review.</div>}
                  </CardContent>
               </Card>
             </div>
          </div>
        )}

        {activeTab === "rejected" && (
          <div className="p-8 flex flex-col h-full gap-6 overflow-hidden">
            <h2 className="text-3xl font-extrabold tracking-tight">Rejection History</h2>
            <Card className="flex-1 bg-white shadow-md overflow-hidden rounded-3xl">
              <div className="h-full overflow-y-auto custom-scrollbar">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b sticky top-0"><tr className="text-left text-slate-500 font-bold uppercase text-[10px]"><th className="p-4">File ID</th><th className="p-4">Timestamp</th><th className="p-4">Auditor Note</th></tr></thead>
                  <tbody>{rejectedHistory.length === 0 ? <tr><td colSpan={3} className="p-10 text-center text-slate-300 italic">No rejections archived.</td></tr> : rejectedHistory.map((inv, i) => (<tr key={i} className="border-b hover:bg-slate-50 transition-colors"><td className="p-4 font-mono font-bold text-blue-600">{inv.id}</td><td className="p-4 text-slate-500">{inv.date}</td><td className="p-4 italic text-slate-500">"{inv.comment || 'N/A'}"</td></tr>))}</tbody>
                </table>
              </div>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}