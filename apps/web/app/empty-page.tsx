export function EmptyPage({ title }: { title: string }) {
  return (
    <main id="main" className="page">
      <h1>{title}</h1>
      <p>未接数据</p>
    </main>
  );
}
