// Template: flat fact partition (replace agg table in semantic model)
let
    Source = Sql.Database(db_address, "glofox_lakehouse"),
    target_table =
        Value.NativeQuery(
            Source,
            "
            WITH branches_selected AS (
                SELECT DISTINCT db.id
                FROM gold_layer.dim_branch_all db
                WHERE db.corporate_id = @corp_id
            )
            SELECT s.*
            FROM gold_layer.{{TABLE_NAME}} s
            INNER JOIN branches_selected b ON b.id = s.branch_id
            WHERE s.{{DATE_COLUMN}} >= DATEADD(YEAR,-1,CAST(GETDATE() AS DATE))
            ",
            [ corp_id = corp_id ],
            [EnableFolding = true]
        ),
    #"Renamed Columns" = Table.RenameColumns(target_table, {{RENAME_MAP}}, MissingField.Ignore)
in
    #"Renamed Columns"
