export default function NoticeFilters({ search, setSearch, agency, setAgency, agencies }) {
  return (
    <div className="filter-row">
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="제목/내용 검색"
      />
      <select value={agency} onChange={(e) => setAgency(e.target.value)}>
        {agencies.map((item) => (
          <option key={item} value={item}>
            {item}
          </option>
        ))}
      </select>
    </div>
  )
}
