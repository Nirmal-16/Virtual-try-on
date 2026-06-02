import { Check } from "lucide-react";
import type { JobStatus } from "../../types";

interface Step {
  label: string;
  statuses: JobStatus[];
  doneStatuses: JobStatus[];
}

const STEPS: Step[] = [
  {
    label: "Upload",
    statuses: ["queued"],
    doneStatuses: [
      "tryon_processing",
      "tryon_done",
      "scene_processing",
      "done",
    ],
  },
  {
    label: "Try-On",
    statuses: ["tryon_processing"],
    doneStatuses: ["tryon_done", "scene_processing", "done"],
  },
  {
    label: "Scene",
    statuses: ["scene_processing"],
    doneStatuses: ["done"],
  },
  {
    label: "Done",
    statuses: ["done"],
    doneStatuses: [],
  },
];

interface Props {
  currentStatus: JobStatus | null;
}

export function ProgressStepper({ currentStatus }: Props) {
  return (
    <div className="flex items-center justify-center gap-0 w-full max-w-2xl mx-auto">
      {STEPS.map((step, i) => {
        const isActive =
          currentStatus !== null && step.statuses.includes(currentStatus);
        const isDone =
          currentStatus !== null && step.doneStatuses.includes(currentStatus);
        const isFirst = i === 0;

        return (
          <div key={step.label} className="flex items-center flex-1 min-w-0">
            {/* Connector line */}
            {!isFirst && (
              <div
                className={`h-0.5 flex-1 transition-colors duration-300 ${
                  isDone ? "bg-rose-500" : "bg-gray-200"
                }`}
              />
            )}

            {/* Step circle */}
            <div className="flex flex-col items-center shrink-0">
              <div
                className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold border-2 transition-all duration-300 ${
                  isDone
                    ? "bg-rose-500 border-rose-500 text-white"
                    : isActive
                    ? "bg-white border-rose-500 text-rose-500 animate-pulse"
                    : "bg-white border-gray-300 text-gray-400"
                }`}
              >
                {isDone ? <Check size={16} /> : i + 1}
              </div>
              <span
                className={`mt-1 text-xs font-medium whitespace-nowrap transition-colors duration-300 ${
                  isActive
                    ? "text-rose-600"
                    : isDone
                    ? "text-rose-500"
                    : "text-gray-400"
                }`}
              >
                {step.label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
