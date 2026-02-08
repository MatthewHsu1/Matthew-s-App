using Polly;

namespace FinancialApp.Application.Extensions
{
    public static class ExceptionRetryExtensions
    {
        /// <summary>
        /// Executes an async action with retry logic for all exceptions
        /// </summary>
        public static async Task RetryAsync(
            this Func<Task> action,
            int retryCount = 3,
            double delaySeconds = 2,
            Func<int, TimeSpan>? delayProvider = null)
        {
            var policy = Policy.Handle<Exception>()
                .WaitAndRetryAsync(retryCount, delayProvider ?? (_ => TimeSpan.FromSeconds(delaySeconds)));
            await policy.ExecuteAsync(action);
        }

        /// <summary>
        /// Executes an async function with retry logic for exceptions matching a specific predicate (e.g. checking message text)
        /// </summary>
        public static async Task RetryAsync(
            this Func<Task> action,
            Func<Exception, bool> exceptionPredicate,
            int retryCount = 3,
            double delaySeconds = 2,
            Func<int, TimeSpan>? delayProvider = null)
        {
            var policy = Policy.Handle(exceptionPredicate)
                .WaitAndRetryAsync(retryCount, delayProvider ?? (_ => TimeSpan.FromSeconds(delaySeconds)));
            await policy.ExecuteAsync(action);
        }

        /// <summary>
        /// Executes an async action with retry logic for one exception type
        /// </summary>
        public static async Task RetryAsync<T1>(
            this Func<Task> action,
            int retryCount = 3,
            double delaySeconds = 2,
            Func<int, TimeSpan>? delayProvider = null)
            where T1 : Exception
        {
            var policy = Policy.Handle<T1>()
                .WaitAndRetryAsync(retryCount, delayProvider ?? (_ => TimeSpan.FromSeconds(delaySeconds)));
            await policy.ExecuteAsync(action);
        }

        /// <summary>
        /// Executes an async action with retry logic for two exception types
        /// </summary>
        public static async Task RetryAsync<T1, T2>(
            this Func<Task> action,
            int retryCount = 3,
            double delaySeconds = 2,
            Func<int, TimeSpan>? delayProvider = null)
            where T1 : Exception
            where T2 : Exception
        {
            var policy = Policy.Handle<T1>()
                .Or<T2>()
                .WaitAndRetryAsync(retryCount, delayProvider ?? (_ => TimeSpan.FromSeconds(delaySeconds)));
            await policy.ExecuteAsync(action);
        }

        /// <summary>
        /// Executes an async action with retry logic for three exception types
        /// </summary>
        public static async Task RetryAsync<T1, T2, T3>(
            this Func<Task> action,
            int retryCount = 3,
            double delaySeconds = 2,
            Func<int, TimeSpan>? delayProvider = null)
            where T1 : Exception
            where T2 : Exception
            where T3 : Exception
        {
            var policy = Policy.Handle<T1>()
                .Or<T2>()
                .Or<T3>()
                .WaitAndRetryAsync(retryCount, delayProvider ?? (_ => TimeSpan.FromSeconds(delaySeconds)));
            await policy.ExecuteAsync(action);
        }

        /// <summary>
        /// Executes an async action with retry logic for four exception types
        /// </summary>
        public static async Task RetryAsync<T1, T2, T3, T4>(
            this Func<Task> action,
            int retryCount = 3,
            double delaySeconds = 2,
            Func<int, TimeSpan>? delayProvider = null)
            where T1 : Exception
            where T2 : Exception
            where T3 : Exception
            where T4 : Exception
        {
            var policy = Policy.Handle<T1>()
                .Or<T2>()
                .Or<T3>()
                .Or<T4>()
                .WaitAndRetryAsync(retryCount, delayProvider ?? (_ => TimeSpan.FromSeconds(delaySeconds)));
            await policy.ExecuteAsync(action);
        }

        /// <summary>
        /// Executes an async action with retry logic for five exception types
        /// </summary>
        public static async Task RetryAsync<T1, T2, T3, T4, T5>(
            this Func<Task> action,
            int retryCount = 3,
            double delaySeconds = 2,
            Func<int, TimeSpan>? delayProvider = null)
            where T1 : Exception
            where T2 : Exception
            where T3 : Exception
            where T4 : Exception
            where T5 : Exception
        {
            var policy = Policy.Handle<T1>()
                .Or<T2>()
                .Or<T3>()
                .Or<T4>()
                .Or<T5>()
                .WaitAndRetryAsync(retryCount, delayProvider ?? (_ => TimeSpan.FromSeconds(delaySeconds)));
            await policy.ExecuteAsync(action);
        }

        /// <summary>
        /// Executes an async function with retry logic for all exceptions and returns result
        /// </summary>
        public static async Task<TResult> RetryAsync<TResult>(
            this Func<Task<TResult>> action,
            int retryCount = 3,
            double delaySeconds = 2,
            Func<int, TimeSpan>? delayProvider = null)
        {
            var policy = Policy.Handle<Exception>()
                .WaitAndRetryAsync(retryCount, delayProvider ?? (_ => TimeSpan.FromSeconds(delaySeconds)));
            return await policy.ExecuteAsync(action);
        }

        /// <summary>
        /// Executes an async function with retry logic for exceptions matching a specific predicate (e.g. checking message text)
        /// </summary>
        public static async Task<TResult> RetryAsync<TResult>(
            this Func<Task<TResult>> action,
            Func<Exception, bool> exceptionPredicate,
            int retryCount = 3,
            double delaySeconds = 2,
            Func<int, TimeSpan>? delayProvider = null)
        {
            var policy = Policy.Handle(exceptionPredicate)
                .WaitAndRetryAsync(retryCount, delayProvider ?? (_ => TimeSpan.FromSeconds(delaySeconds)));
            return await policy.ExecuteAsync(action);
        }

        /// <summary>
        /// Executes an async function with retry logic for one exception type and returns result
        /// </summary>
        public static async Task<TResult> RetryAsync<TResult, T1>(
            this Func<Task<TResult>> action,
            int retryCount = 3,
            double delaySeconds = 2,
            Func<int, TimeSpan>? delayProvider = null)
            where T1 : Exception
        {
            var policy = Policy.Handle<T1>()
                .WaitAndRetryAsync(retryCount, delayProvider ?? (_ => TimeSpan.FromSeconds(delaySeconds)));
            return await policy.ExecuteAsync(action);
        }

        /// <summary>
        /// Executes an async function with retry logic for two exception types and returns result
        /// </summary>
        public static async Task<TResult> RetryAsync<TResult, T1, T2>(
            this Func<Task<TResult>> action,
            int retryCount = 3,
            double delaySeconds = 2,
            Func<int, TimeSpan>? delayProvider = null)
            where T1 : Exception
            where T2 : Exception
        {
            var policy = Policy.Handle<T1>()
                .Or<T2>()
                .WaitAndRetryAsync(retryCount, delayProvider ?? (_ => TimeSpan.FromSeconds(delaySeconds)));
            return await policy.ExecuteAsync(action);
        }

        /// <summary>
        /// Executes an async function with retry logic for three exception types and returns result
        /// </summary>
        public static async Task<TResult> RetryAsync<TResult, T1, T2, T3>(
            this Func<Task<TResult>> action,
            int retryCount = 3,
            double delaySeconds = 2,
            Func<int, TimeSpan>? delayProvider = null)
            where T1 : Exception
            where T2 : Exception
            where T3 : Exception
        {
            var policy = Policy.Handle<T1>()
                .Or<T2>()
                .Or<T3>()
                .WaitAndRetryAsync(retryCount, delayProvider ?? (_ => TimeSpan.FromSeconds(delaySeconds)));
            return await policy.ExecuteAsync(action);
        }

        /// <summary>
        /// Executes an async function with retry logic for four exception types and returns result
        /// </summary>
        public static async Task<TResult> RetryAsync<TResult, T1, T2, T3, T4>(
            this Func<Task<TResult>> action,
            int retryCount = 3,
            double delaySeconds = 2,
            Func<int, TimeSpan>? delayProvider = null)
            where T1 : Exception
            where T2 : Exception
            where T3 : Exception
            where T4 : Exception
        {
            var policy = Policy.Handle<T1>()
                .Or<T2>()
                .Or<T3>()
                .Or<T4>()
                .WaitAndRetryAsync(retryCount, delayProvider ?? (_ => TimeSpan.FromSeconds(delaySeconds)));
            return await policy.ExecuteAsync(action);
        }

        /// <summary>
        /// Executes an async function with retry logic for five exception types and returns result
        /// </summary>
        public static async Task<TResult> RetryAsync<TResult, T1, T2, T3, T4, T5>(
            this Func<Task<TResult>> action,
            int retryCount = 3,
            double delaySeconds = 2,
            Func<int, TimeSpan>? delayProvider = null)
            where T1 : Exception
            where T2 : Exception
            where T3 : Exception
            where T4 : Exception
            where T5 : Exception
        {
            var policy = Policy.Handle<T1>()
                .Or<T2>()
                .Or<T3>()
                .Or<T4>()
                .Or<T5>()
                .WaitAndRetryAsync(retryCount, delayProvider ?? (_ => TimeSpan.FromSeconds(delaySeconds)));
            return await policy.ExecuteAsync(action);
        }
    }
}
