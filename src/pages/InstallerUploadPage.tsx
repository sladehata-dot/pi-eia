import React, { useState, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { supabase } from '@/lib/supabase';
import { CheckCircle, Upload, AlertCircle, FileText, Shield, Briefcase, Building2, ChevronDown, ChevronUp, Loader2, X } from 'lucide-react';

// ── Document categories (mirroring the Installer Agreement Clauses 4 & 7) ──────
const DOCUMENT_CATEGORIES = [
  {
    id: 'accreditations',
    label: 'SAA / CEC Accreditation',
    icon: Shield,
    color: 'cyan',
    folderPath: 'Accreditations',
    items: [
      { id: 'saa_cert', label: 'SAA / CEC Accreditation Certificate', hint: 'Current – shows accreditation number & expiry date', required: true },
      { id: 'design_accred', label: 'Design Accreditation Certificate', hint: 'Required only if engaged as system designer', required: false },
    ],
  },
  {
    id: 'licences',
    label: 'Electrical Licences',
    icon: FileText,
    color: 'blue',
    folderPath: 'Licences',
    items: [
      { id: 'contractor_licence', label: 'Electrical Contractor Licence', hint: 'Certified copy of current licence', required: true },
      { id: 'work_licence', label: 'Electrical Work Licence', hint: 'Certified copy of current licence', required: true },
      { id: 'other_licence', label: 'Additional Trade Licences', hint: 'Any other licences relevant to scope (if applicable)', required: false },
    ],
  },
  {
    id: 'insurance',
    label: 'Insurance – Certificates of Currency',
    icon: Briefcase,
    color: 'amber',
    folderPath: 'Insurance',
    items: [
      { id: 'public_liability', label: 'Public Liability Insurance', hint: 'Min. $10M | Certificate of Currency – policy no., insurer, cover dates', required: true },
      { id: 'workers_comp', label: 'Workers Compensation / Workplace Cover', hint: 'Certificate of Currency', required: true },
      { id: 'prof_indemnity', label: 'Professional Indemnity Insurance', hint: 'Certificate of Currency (if applicable)', required: false },
    ],
  },
  {
    id: 'company',
    label: 'Company / Business Documents',
    icon: Building2,
    color: 'violet',
    folderPath: 'Company Documents',
    items: [
      { id: 'abn_confirm', label: 'ABN / ACN Confirmation', hint: 'ASIC company extract or current ABN lookup printout', required: true },
      { id: 'bank_details', label: 'Bank Account Details', hint: 'BSB & Account Number for payment processing (secure document)', required: true },
    ],
  },
];

type UploadStatus = 'idle' | 'uploading' | 'done' | 'error';

interface FileState {
  file: File;
  status: UploadStatus;
  progress: number;
  error?: string;
  storagePath?: string;
}

type FileMap = Record<string, FileState[]>; // itemId → files[]

const colorMap: Record<string, string> = {
  cyan:   'border-cyan-500/40 bg-cyan-500/5',
  blue:   'border-blue-500/40 bg-blue-500/5',
  amber:  'border-amber-500/40 bg-amber-500/5',
  violet: 'border-violet-500/40 bg-violet-500/5',
};

const iconColorMap: Record<string, string> = {
  cyan:   'text-cyan-400',
  blue:   'text-blue-400',
  amber:  'text-amber-400',
  violet: 'text-violet-400',
};

const badgeColorMap: Record<string, string> = {
  cyan:   'bg-cyan-500/20 text-cyan-300',
  blue:   'bg-blue-500/20 text-blue-300',
  amber:  'bg-amber-500/20 text-amber-300',
  violet: 'bg-violet-500/20 text-violet-300',
};

// ── Helpers ──────────────────────────────────────────────────────────────────
function sanitizePath(str: string): string {
  return str.replace(/[^a-zA-Z0-9_\-. ]/g, '_');
}

function countUploaded(fileMap: FileMap): number {
  return Object.values(fileMap).reduce((sum, files) =>
    sum + files.filter(f => f.status === 'done').length, 0);
}

function totalRequired(): number {
  return DOCUMENT_CATEGORIES.flatMap(c => c.items.filter(i => i.required)).length;
}

function requiredDone(fileMap: FileMap): boolean {
  for (const cat of DOCUMENT_CATEGORIES) {
    for (const item of cat.items) {
      if (item.required) {
        const files = fileMap[item.id] || [];
        if (!files.some(f => f.status === 'done')) return false;
      }
    }
  }
  return true;
}

// ── File Drop Zone ────────────────────────────────────────────────────────────
interface DropZoneProps {
  itemId: string;
  files: FileState[];
  onFiles: (itemId: string, files: File[]) => void;
  onRemove: (itemId: string, idx: number) => void;
  disabled?: boolean;
}

const DropZone: React.FC<DropZoneProps> = ({ itemId, files, onFiles, onRemove, disabled }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    const dropped = Array.from(e.dataTransfer.files);
    if (dropped.length) onFiles(itemId, dropped);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    if (selected.length) onFiles(itemId, selected);
    e.target.value = '';
  };

  const hasUploaded = files.some(f => f.status === 'done');

  return (
    <div className="mt-2">
      {/* File list */}
      {files.length > 0 && (
        <div className="mb-2 space-y-1">
          {files.map((f, idx) => (
            <div key={idx} className="flex items-center gap-2 bg-slate-700/50 rounded-lg px-3 py-2">
              <div className="flex-1 min-w-0">
                <p className="text-xs text-slate-200 truncate">{f.file.name}</p>
                {f.status === 'uploading' && (
                  <div className="mt-1 h-1 bg-slate-600 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-cyan-400 transition-all duration-300"
                      style={{ width: `${f.progress}%` }}
                    />
                  </div>
                )}
                {f.status === 'error' && (
                  <p className="text-xs text-red-400 mt-0.5">{f.error}</p>
                )}
              </div>
              <div className="flex-shrink-0">
                {f.status === 'uploading' && <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />}
                {f.status === 'done'      && <CheckCircle className="w-4 h-4 text-emerald-400" />}
                {f.status === 'error'     && <AlertCircle className="w-4 h-4 text-red-400" />}
                {(f.status === 'idle' || f.status === 'error') && (
                  <button onClick={() => onRemove(itemId, idx)} className="ml-1 text-slate-500 hover:text-slate-300">
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Drop target */}
      {!hasUploaded && (
        <div
          onClick={() => !disabled && inputRef.current?.click()}
          onDragOver={e => { e.preventDefault(); if (!disabled) setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={`
            border-2 border-dashed rounded-lg px-4 py-3 text-center cursor-pointer transition-colors
            ${dragging ? 'border-cyan-400 bg-cyan-400/10' : 'border-slate-600 hover:border-slate-400 bg-slate-800/40'}
            ${disabled ? 'opacity-40 cursor-not-allowed' : ''}
          `}
        >
          <Upload className="w-4 h-4 text-slate-400 mx-auto mb-1" />
          <p className="text-xs text-slate-400">
            Drop file here or <span className="text-cyan-400 underline">browse</span>
          </p>
          <p className="text-[10px] text-slate-600 mt-0.5">PDF, JPG, PNG accepted</p>
        </div>
      )}

      {hasUploaded && (
        <button
          onClick={() => !disabled && inputRef.current?.click()}
          disabled={disabled}
          className="text-xs text-cyan-400 hover:text-cyan-300 mt-1 underline"
        >
          + Add another file
        </button>
      )}

      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.jpg,.jpeg,.png,.heic"
        className="hidden"
        onChange={handleChange}
        disabled={disabled}
      />
    </div>
  );
};

// ── Main Page ─────────────────────────────────────────────────────────────────
const InstallerUploadPage: React.FC = () => {
  const [searchParams] = useSearchParams();

  const installerName  = searchParams.get('installer') || '';
  const companyName    = searchParams.get('company')   || '';
  const agreementDate  = searchParams.get('date')      || '';

  const displayName = companyName || installerName || 'Installer';
  const folderRoot  = sanitizePath(companyName || installerName || 'unknown');

  const [fileMap,   setFileMap]   = useState<FileMap>({});
  const [expanded,  setExpanded]  = useState<Record<string, boolean>>(
    Object.fromEntries(DOCUMENT_CATEGORIES.map(c => [c.id, true]))
  );
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // ── Upload a single file to Supabase Storage ────────────────────────────────
  const uploadFile = useCallback(
    async (itemId: string, fileIdx: number, file: File, folderPath: string) => {
      const timestamp  = Date.now();
      const safeName   = sanitizePath(file.name);
      const storagePath = `${folderRoot}/${sanitizePath(folderPath)}/${timestamp}_${safeName}`;

      // Mark uploading
      setFileMap(prev => {
        const updated = { ...prev };
        const arr = [...(updated[itemId] || [])];
        arr[fileIdx] = { ...arr[fileIdx], status: 'uploading', progress: 10 };
        updated[itemId] = arr;
        return updated;
      });

      // Simulate progress tick at 40%
      await new Promise(r => setTimeout(r, 300));
      setFileMap(prev => {
        const updated = { ...prev };
        const arr = [...(updated[itemId] || [])];
        if (arr[fileIdx]) arr[fileIdx] = { ...arr[fileIdx], progress: 40 };
        updated[itemId] = arr;
        return updated;
      });

      const { error } = await supabase.storage
        .from('installer-documents')
        .upload(storagePath, file, { upsert: true, contentType: file.type });

      if (error) {
        setFileMap(prev => {
          const updated = { ...prev };
          const arr = [...(updated[itemId] || [])];
          arr[fileIdx] = { ...arr[fileIdx], status: 'error', progress: 0, error: error.message };
          updated[itemId] = arr;
          return updated;
        });
        return;
      }

      setFileMap(prev => {
        const updated = { ...prev };
        const arr = [...(updated[itemId] || [])];
        arr[fileIdx] = { ...arr[fileIdx], status: 'done', progress: 100, storagePath };
        updated[itemId] = arr;
        return updated;
      });
    },
    [folderRoot]
  );

  // ── Handle new files added to a slot ───────────────────────────────────────
  const handleFiles = useCallback(
    (itemId: string, newFiles: File[]) => {
      // Find which category/item this belongs to for the folder path
      const cat  = DOCUMENT_CATEGORIES.find(c => c.items.some(i => i.id === itemId));
      const item = cat?.items.find(i => i.id === itemId);
      if (!cat || !item) return;

      setFileMap(prev => {
        const existing = prev[itemId] || [];
        const appended: FileState[] = newFiles.map(f => ({ file: f, status: 'idle', progress: 0 }));
        return { ...prev, [itemId]: [...existing, ...appended] };
      });

      // Kick off uploads after state settles
      setFileMap(prev => {
        const arr = prev[itemId] || [];
        const startIdx = arr.length - newFiles.length;
        newFiles.forEach((file, offset) => {
          uploadFile(itemId, startIdx + offset, file, cat.folderPath);
        });
        return prev;
      });

      // Upload each new file
      setFileMap(currentMap => {
        const startIdx = (currentMap[itemId] || []).length - newFiles.length;
        newFiles.forEach((file, offset) => {
          uploadFile(itemId, startIdx + offset, file, cat.folderPath);
        });
        return currentMap;
      });
    },
    [uploadFile]
  );

  // ── Remove a file (only for idle/error states) ─────────────────────────────
  const handleRemove = (itemId: string, idx: number) => {
    setFileMap(prev => {
      const arr = [...(prev[itemId] || [])];
      arr.splice(idx, 1);
      return { ...prev, [itemId]: arr };
    });
  };

  // ── Mark submission complete ───────────────────────────────────────────────
  const handleSubmit = async () => {
    setSubmitting(true);
    // Log submission record to Supabase
    try {
      await supabase.from('installer_onboarding_submissions').insert({
        installer_name : installerName,
        company_name   : companyName,
        agreement_date : agreementDate,
        submitted_at   : new Date().toISOString(),
        storage_folder : folderRoot,
        files_uploaded : countUploaded(fileMap),
      });
    } catch (_) {
      // Non-blocking — submission still completes even if logging fails
    }
    setSubmitting(false);
    setSubmitted(true);
  };

  const toggle = (id: string) =>
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }));

  const uploadedCount = countUploaded(fileMap);
  const requiredCount = totalRequired();
  const allRequiredDone = requiredDone(fileMap);

  // ── Submitted confirmation screen ─────────────────────────────────────────
  if (submitted) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-6">
        <div className="max-w-md w-full text-center">
          <div className="w-20 h-20 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="w-10 h-10 text-emerald-400" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-3">Documents Received</h2>
          <p className="text-slate-400 mb-2">
            Thank you, <strong className="text-white">{displayName}</strong>.
          </p>
          <p className="text-slate-400 mb-6">
            Your compliance documents have been submitted successfully.
            Pi Ops will review and confirm your installer activation by email.
          </p>
          <div className="bg-slate-800 rounded-xl p-4 text-left text-sm">
            <p className="text-slate-400">
              Questions? Contact&nbsp;
              <a href="mailto:slade@principleinnovation.tech" className="text-cyan-400 underline">
                slade@principleinnovation.tech
              </a>
            </p>
          </div>
          <p className="text-slate-600 text-xs mt-6">
            Pi Ops Pty Ltd &nbsp;·&nbsp; ABN 85 685 996 114
          </p>
        </div>
      </div>
    );
  }

  // ── Main upload page ───────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-900 pb-20">

      {/* Header */}
      <div className="bg-slate-800 border-b border-slate-700">
        <div className="max-w-3xl mx-auto px-6 py-5 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-6 h-6 bg-cyan-500/20 rounded-full flex items-center justify-center">
                <div className="w-3 h-3 bg-cyan-400 rounded-full" />
              </div>
              <span className="text-slate-400 text-xs font-medium uppercase tracking-widest">
                Pi Ops · Installer Onboarding
              </span>
            </div>
            <h1 className="text-xl font-bold text-white leading-tight">
              Compliance Document Upload
            </h1>
            {displayName && (
              <p className="text-slate-400 text-sm mt-0.5">
                {displayName}
                {agreementDate && <span className="text-slate-600"> · Agreement dated {agreementDate}</span>}
              </p>
            )}
          </div>

          {/* Progress pill */}
          <div className="flex-shrink-0 text-right">
            <div className="inline-flex items-center gap-2 bg-slate-700 rounded-full px-3 py-1.5">
              <div className={`w-2 h-2 rounded-full ${allRequiredDone ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              <span className="text-xs text-slate-300 font-medium">
                {uploadedCount} / {requiredCount} required
              </span>
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="max-w-3xl mx-auto px-6 pb-4">
          <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-500"
              style={{ width: `${Math.min(100, (uploadedCount / requiredCount) * 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Instructions banner */}
      <div className="max-w-3xl mx-auto px-6 pt-5">
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4 mb-6">
          <p className="text-sm text-blue-300 leading-relaxed">
            <strong>Action required:</strong> Upload the compliance documents below to activate your
            Pi Installer profile. Required items are marked with&nbsp;<span className="text-red-400">*</span>.
            All documents must be <strong>current and valid</strong>.
            No Work Orders can be issued until all required items have been received and verified.
          </p>
        </div>
      </div>

      {/* Document categories */}
      <div className="max-w-3xl mx-auto px-6 space-y-4">
        {DOCUMENT_CATEGORIES.map(cat => {
          const Icon = cat.icon;
          const isOpen = expanded[cat.id];
          const catFiles = cat.items.flatMap(i => fileMap[i.id] || []);
          const catDone  = catFiles.filter(f => f.status === 'done').length;
          const catTotal = cat.items.filter(i => i.required).length;

          return (
            <div
              key={cat.id}
              className={`border rounded-xl overflow-hidden ${colorMap[cat.color]}`}
            >
              {/* Category header */}
              <button
                onClick={() => toggle(cat.id)}
                className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-white/5 transition-colors"
              >
                <Icon className={`w-5 h-5 flex-shrink-0 ${iconColorMap[cat.color]}`} />
                <span className="flex-1 font-semibold text-white text-sm">{cat.label}</span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${badgeColorMap[cat.color]}`}>
                  {catDone}/{catTotal} required
                </span>
                {isOpen
                  ? <ChevronUp   className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  : <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />}
              </button>

              {/* Items */}
              {isOpen && (
                <div className="px-5 pb-5 space-y-5 border-t border-slate-700/50 pt-4">
                  {cat.items.map(item => {
                    const files = fileMap[item.id] || [];
                    const isDone = files.some(f => f.status === 'done');

                    return (
                      <div key={item.id}>
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <div>
                            <span className="text-sm text-slate-200 font-medium">
                              {item.label}
                              {item.required && <span className="text-red-400 ml-0.5">*</span>}
                            </span>
                            <p className="text-xs text-slate-500 mt-0.5">{item.hint}</p>
                          </div>
                          {isDone && (
                            <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                          )}
                        </div>
                        <DropZone
                          itemId={item.id}
                          files={files}
                          onFiles={handleFiles}
                          onRemove={handleRemove}
                          disabled={submitting}
                        />
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Submit bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-slate-800/95 backdrop-blur border-t border-slate-700 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between gap-4">
          <div>
            {allRequiredDone ? (
              <p className="text-sm text-emerald-400 font-medium">
                ✓ All required documents uploaded
              </p>
            ) : (
              <p className="text-sm text-slate-400">
                Upload all required documents to submit
              </p>
            )}
            {uploadedCount > 0 && !allRequiredDone && (
              <p className="text-xs text-slate-500 mt-0.5">
                {requiredCount - uploadedCount > 0
                  ? `${requiredCount - Math.min(uploadedCount, requiredCount)} required item(s) remaining`
                  : 'Optional items can also be added'}
              </p>
            )}
          </div>

          <button
            onClick={handleSubmit}
            disabled={!allRequiredDone || submitting}
            className={`
              flex items-center gap-2 px-6 py-2.5 rounded-lg font-semibold text-sm transition-all
              ${allRequiredDone && !submitting
                ? 'bg-cyan-500 hover:bg-cyan-400 text-white shadow-lg shadow-cyan-500/25'
                : 'bg-slate-700 text-slate-500 cursor-not-allowed'}
            `}
          >
            {submitting
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting...</>
              : <><CheckCircle className="w-4 h-4" /> Submit Documents</>
            }
          </button>
        </div>
      </div>
    </div>
  );
};

export default InstallerUploadPage;
