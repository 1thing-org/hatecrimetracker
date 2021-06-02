CREATE TABLE public.incidents (
    id serial PRIMARY KEY,
	incident_time TIMESTAMP NOT NULL,
    created_on TIMESTAMP NOT NULL,
	title varchar(1024) NOT NULL,
	abstract varchar(1024) NOT NULL,
	incident_location varchar(256) NULL,
	url varchar(1024) NULL,
	incident_source varchar(64) NOT NULL
);
CREATE INDEX incident_time_idx ON public.incidents (incident_time);
CREATE INDEX incident_location_idx ON public.incidents (incident_location, incident_time);

-- Column comments

COMMENT ON COLUMN public.incidents.incident_location IS '2 char State code';
COMMENT ON COLUMN public.incidents.url IS 'Link to the original website';
COMMENT ON COLUMN public.incidents.incident_source IS 'A short name of the source type, such as NEWS|CNN|FBI|NYPD_TWITTER|NYPD_DB, etc. Will use to help assess reliability of the data. Each crawler will pick a unique source for data it cralws from.';
