import type { ReactNode } from "react";
import Navbar from "./Navbar";

interface Props {
  children: ReactNode;
  navbarRight?: ReactNode;
  /** Fill viewport with no page scroll (simulation dashboard) */
  fill?: boolean;
}

export default function PageLayout({ children, navbarRight, fill }: Props) {
  return (
    <div className="h-full flex flex-col">
      <Navbar right={navbarRight} />
      <main className={fill ? "flex-1 min-h-0 overflow-hidden" : "flex-1 overflow-y-auto"}>
        {children}
      </main>
    </div>
  );
}
