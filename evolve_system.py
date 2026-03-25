from system.evolve_system import main, parse_args


if __name__ == "__main__":
    args = parse_args()
    main(
        iterations=args.iterations if args.iterations is not None else 3,
        candidates_per_round=args.candidates_per_round if args.candidates_per_round is not None else 30,
        feedback_per_class=args.feedback_per_class if args.feedback_per_class is not None else 5,
        data_path=args.data_path,
        output_dir=args.output_dir,
        seed=args.seed,
        dry_run=args.dry_run,
    )
