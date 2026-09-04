import { Suspense } from "react";

import { Workbench } from "./workbench";

export default function GraphPage() {
  return (
    <Suspense
      fallback={
        <main className="gw gw-fallback" aria-busy="true">
          载入图谱工作台
        </main>
      }
    >
      <Workbench />
    </Suspense>
  );
}
