import { useCallback, useState } from "react";
import { Icon } from "./icons";
import SyncPanel from "./SyncPanel";

/**
 * Кнопка «Загрузить вакансии» в шапке. Разворачивается в панель с настройками,
 * чтобы основной интерфейс не загромождался. Не работает вне режима «Данные сервиса».
 */
export default function SyncHeaderButton({
  active,
  onLoaded,
  onBlocked,
}: {
  active: boolean;
  onLoaded: () => void;
  /** Вызывается, если пользователь нажал кнопку не в режиме «Данные сервиса». */
  onBlocked: (message: string) => void;
}) {
  const [open, setOpen] = useState(false);

  const toggle = useCallback(() => {
    if (!active) {
      onBlocked("Переключитесь на вкладку «Данные сервиса», чтобы загрузить вакансии с портала.");
      return;
    }
    setOpen((current) => !current);
  }, [active, onBlocked]);

  const handleDone = useCallback(() => {
    onLoaded();
  }, [onLoaded]);

  return (
    <>
      <button
        type="button"
        className="button sync-panel__toggle"
        aria-expanded={open}
        aria-controls="sync-panel"
        onClick={toggle}
      >
        <Icon name="download" size={15} /> Загрузить вакансии
      </button>

      {open && active ? (
        <div className="sync-panel__wrap" id="sync-panel">
          <SyncPanel onDone={handleDone} />
        </div>
      ) : null}
    </>
  );
}
