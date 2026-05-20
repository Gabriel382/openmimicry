/**
 * `<TaskCard />` — task feed driven by `task.card` messages.
 *
 * Each row shows summary (the `note` field), status, an optional
 * progress bar (`progress` in [0,1]), and a Cancel button that sends
 * `{ type: "task.cancel", handle }`.
 *
 * Terminal statuses (`succeeded`, `failed`, `cancelled`) gray out the
 * row and hide the Cancel button.
 */

import { useTaskCards } from "../hooks/useTaskCards";
import type { TaskUpdate } from "../ws/protocol";

const TERMINAL = new Set<TaskUpdate["status"]>(["succeeded", "failed", "cancelled"]);

export interface TaskCardProps {
  className?: string;
}

export function TaskCard(props: TaskCardProps): JSX.Element {
  const { cards, cancel } = useTaskCards();
  if (cards.length === 0) {
    return (
      <div className={`task-card task-card--empty ${props.className ?? ""}`} role="list">
        <span className="task-card__empty-note">No tasks running.</span>
      </div>
    );
  }
  return (
    <div className={`task-card ${props.className ?? ""}`} role="list">
      {cards.map((card) => {
        const terminal = TERMINAL.has(card.status);
        return (
          <div
            key={card.handle.id}
            role="listitem"
            className={`task-card__row task-card__row--${card.status}`}
            data-status={card.status}
            data-handle-id={card.handle.id}
          >
            <span className="task-card__runtime">{card.handle.runtime}</span>
            <span className="task-card__note">{card.note ?? card.status}</span>
            <span className="task-card__status">{card.status}</span>
            {typeof card.progress === "number" && (
              <progress
                value={Math.max(0, Math.min(1, card.progress))}
                max={1}
                aria-label={`progress for ${card.handle.id}`}
              />
            )}
            {card.error && (
              <span className="task-card__error" role="alert">
                {card.error.code}: {card.error.message}
              </span>
            )}
            {!terminal && (
              <button
                type="button"
                aria-label={`cancel ${card.handle.id}`}
                onClick={() => cancel(card.handle.id)}
              >
                Cancel
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
