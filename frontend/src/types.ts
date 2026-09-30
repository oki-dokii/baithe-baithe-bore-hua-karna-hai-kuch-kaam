export type Component = { state: string; detail: string | null };

export type Status = {
  environment: string;
  source_mode: string;
  database: Component;
  spatial: Component;
  vector: Component;
  ingestion: Component;
  replay: Component;
  prediction: Component;
  datasets: string[];
  checked_at: string;
};

export type Well = {
  id: string;
  external_id: string;
  name: string;
  basin_name: string | null;
  data_kind: string;
  longitude: number;
  latitude: number;
  surface_distance_m: number | null;
};

export type WellPage = { items: Well[]; next_cursor: string | null };
